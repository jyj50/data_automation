"""
Core PDF processing and RAG preparation utilities.
- Upload ingestion: checksum, page extraction, cleaning, preview generation
- Structured parsing (regex-first, optional LLM refinement) into Article units
- Chunking per-Article with overlap
- Embedding/upsert + question generation stubs (env-configurable)
"""

import hashlib
import json
import logging
import os
import re
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import chromadb
import fitz  # PyMuPDF
import httpx
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from .models import (
    Article,
    ArticleChunk,
    Document,
    DocumentChunk,
    DocumentPage,
    DocumentStatus,
    GeneratedQuestion,
    ProcessingStatus,
)

logger = logging.getLogger(__name__)

# Regex patterns for Korean law-like structures
CHAPTER_PATTERN = re.compile(r"^\uC81C\s*\d+\s*\uC7A5\b.*")
SECTION_PATTERN = re.compile(r"^\uC81C\s*\d+\s*\uC808\b.*")
ARTICLE_PATTERN = re.compile(r"^(\uC81C\s*\d+\s*\uC870(?:\uC758\s*\d+)?)(\s*\([^)]*\))?(.*)$")


class ArticlePayload(BaseModel):
    article_key: str
    title: Optional[str] = None
    full_title: str
    content: str
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None
    source_pages: List[int]
    warnings: List[str] = []


class DocumentParsePayload(BaseModel):
    articles: List[ArticlePayload]
    global_warnings: List[str] = []


def compute_checksum(file_obj) -> str:
    """Return SHA-256 checksum for an UploadedFile or file-like object."""
    hasher = hashlib.sha256()
    position = None

    if hasattr(file_obj, "tell"):
        try:
            position = file_obj.tell()
        except Exception:
            position = None

    try:
        if hasattr(file_obj, "chunks"):
            for chunk in file_obj.chunks():
                hasher.update(chunk)
        else:
            while True:
                chunk = file_obj.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
    finally:
        if position is not None and hasattr(file_obj, "seek"):
            file_obj.seek(position)
    return hasher.hexdigest()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def extract_pdf_pages(file_path: str) -> List[str]:
    """Extract raw text per page using PyMuPDF."""
    with fitz.open(file_path) as doc:
        return [page.get_text("text") or "" for page in doc]


def render_page_previews(document: Document) -> Dict[int, str]:
    """
    Render per-page PNG previews for the document.
    Returns mapping {page_no: relative_path}.
    """
    previews: Dict[int, str] = {}
    output_root = os.path.join("documents", str(document.id), "pages")
    full_root = os.path.join(settings.MEDIA_ROOT, output_root)
    _ensure_dir(full_root)

    with fitz.open(document.file.path) as pdf:
        for idx, page in enumerate(pdf, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # slight upscaling for readability
            filename = f"page_{idx:04d}.png"
            rel_path = os.path.join(output_root, filename)
            pix.save(os.path.join(full_root, filename))
            previews[idx] = rel_path.replace("\\", "/")
    return previews


def _strip_repeated_lines(pages: Sequence[str], min_ratio: float = 0.6) -> List[str]:
    """
    Remove lines that repeat across many pages (rough header/footer removal).
    Lines present in at least `min_ratio` of pages are dropped.
    """
    if not pages:
        return []

    from collections import Counter

    line_counts = Counter()
    page_lines: List[List[str]] = []
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        line_counts.update(set(lines))
        page_lines.append(lines)

    threshold = max(2, int(len(pages) * min_ratio))
    repeated = {line for line, count in line_counts.items() if count >= threshold}

    cleaned_pages = []
    for lines in page_lines:
        filtered = [line for line in lines if line not in repeated]
        cleaned_pages.append("\n".join(filtered))
    return cleaned_pages


def clean_page_texts(pages: Sequence[str]) -> List[str]:
    """Normalize whitespace and drop repeated header/footer lines."""
    repeated_stripped = _strip_repeated_lines(pages)
    cleaned = []
    for page in repeated_stripped:
        text = page.replace("\ufeff", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        cleaned.append(text)
    return cleaned


def _persist_pages(
    document: Document,
    raw_pages: Sequence[str],
    clean_pages: Sequence[str],
    previews: Optional[Dict[int, str]] = None,
) -> None:
    DocumentPage.objects.filter(document=document).delete()
    page_objs = []
    for idx, (raw, clean) in enumerate(zip(raw_pages, clean_pages), start=1):
        preview_path = ""
        if previews and idx in previews:
            preview_path = previews[idx]
        page_objs.append(
            DocumentPage(
                document=document,
                page_number=idx,
                text_raw=raw,
                text_clean=clean,
                preview_image_path=preview_path,
            )
        )
    if page_objs:
        DocumentPage.objects.bulk_create(page_objs)


def _normalize_content_lines(lines: Sequence[str]) -> str:
    """
    Conservative normalization: trim, collapse multiple spaces,
    keep numbering/line breaks to avoid over-merging clauses.
    """
    normalized: List[str] = []
    for line in lines:
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        if not cleaned:
            continue
        normalized.append(cleaned)
    return "\n".join(normalized)


def regex_structure_pages(
    pages: Sequence[Tuple[int, str]],
) -> DocumentParsePayload:
    """
    Rule-based segmentation into Article candidates using regex patterns.
    Returns DocumentParsePayload (Pydantic validated).
    """
    articles: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None

    for page_no, text in pages:
        lines = [ln.strip() for ln in text.splitlines()]
        for line in lines:
            if not line:
                continue
            if CHAPTER_PATTERN.match(line):
                chapter_title = line.strip()
                continue
            if SECTION_PATTERN.match(line):
                section_title = line.strip()
                continue

            match = ARTICLE_PATTERN.match(line)
            if match:
                if current:
                    current["content"] = _normalize_content_lines(current.get("content_lines", []))
                    articles.append(current)

                article_key_raw = match.group(1) or ""
                article_key = re.sub(r"\s+", "", article_key_raw)
                paren = match.group(2) or ""
                after_title = (match.group(3) or "").strip()

                current = {
                    "article_key": article_key,
                    "title": paren.strip(" ()"),
                    "full_title": f"{article_key}{paren}".strip(),
                    "content_lines": [after_title] if after_title else [],
                    "chapter_title": chapter_title or "",
                    "section_title": section_title or "",
                    "source_pages": [page_no],
                    "warnings": [],
                }
                continue

            if current:
                current.setdefault("content_lines", []).append(line)
                if page_no not in current["source_pages"]:
                    current["source_pages"].append(page_no)

    if current:
        current["content"] = _normalize_content_lines(current.get("content_lines", []))
        articles.append(current)

    payload = {
        "articles": [
            {
                "article_key": item["article_key"],
                "title": item.get("title") or None,
                "full_title": item.get("full_title") or item["article_key"],
                "content": item.get("content", ""),
                "chapter_title": item.get("chapter_title") or None,
                "section_title": item.get("section_title") or None,
                "source_pages": item.get("source_pages") or [],
                "warnings": item.get("warnings") or [],
            }
            for item in articles
        ],
        "global_warnings": [],
    }
    return DocumentParsePayload(**payload)


def _extract_json_block(text: str) -> str:
    """Attempt to extract JSON substring from an LLM response."""
    if not text:
        raise ValueError("Empty LLM response")
    fence = re.search(r"\{.*\}", text, flags=re.S)
    if fence:
        return fence.group(0)
    return text


def _call_openai_compatible(messages: List[Dict[str, str]]) -> Optional[str]:
    provider = getattr(settings, "LLM_PROVIDER", "openai_compat")
    if provider == "none":
        return None

    base_url = getattr(settings, "LLM_BASE_URL", "")
    model = getattr(settings, "LLM_MODEL", "Qwen2.5-7B-Instruct")
    api_key = getattr(settings, "LLM_API_KEY", "")
    timeout = int(getattr(settings, "LLM_TIMEOUT_SECONDS", 30))

    if not base_url:
        logger.info("LLM base URL missing; skip LLM refinement.")
        return None

    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("No choices returned from LLM")
        content = choices[0].get("message", {}).get("content", "")
        return content


def refine_with_llm(
    base_text: str, regex_payload: DocumentParsePayload
) -> Optional[DocumentParsePayload]:
    """Send regex candidates to LLM for light correction; fallback on validation errors."""
    candidate_keys = {a.article_key for a in regex_payload.articles}
    user_payload = {
        "regex_candidates": [a.dict() for a in regex_payload.articles],
        "full_text": base_text[:20000],  # safety truncate
        "candidate_keys": sorted(candidate_keys),
    }
    system_prompt = (
        "You are a Korean legal document structuring assistant. "
        "Use ONLY provided candidate article keys. "
        "Do NOT invent new articles or change keys. "
        "Return strict JSON matching the schema. "
        "Content must only rearrange/clean provided text."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False),
        },
    ]

    attempts = 0
    last_error: Optional[Exception] = None
    while attempts < 2:
        try:
            raw = _call_openai_compatible(messages)
            if raw is None:
                return None
            parsed = _extract_json_block(raw)
            payload = DocumentParsePayload(**json.loads(parsed))
            filtered_articles = [
                art for art in payload.articles if art.article_key in candidate_keys
            ]
            return DocumentParsePayload(
                articles=filtered_articles,
                global_warnings=payload.global_warnings,
            )
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            attempts += 1
            last_error = exc
            messages.append(
                {
                    "role": "user",
                    "content": "?전 출력???키마? ?반?습?다. ?키마에 맞는 JSON?출력?세??",
                }
            )
            continue
        except Exception as exc:  # network/HTTP errors
            logger.warning("LLM refinement failed: %s", exc)
            return None
    if last_error:
        logger.warning("LLM refinement failed after retry: %s", last_error)
    return None


def chunk_text_with_overlap(text: str, chunk_size: int, overlap: int) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    chunks: List[str] = []
    position = 0
    text_length = len(text)
    while position < text_length:
        end = min(position + chunk_size, text_length)
        slice_text = text[position:end].strip()
        if slice_text:
            chunks.append(slice_text)
        if end >= text_length:
            break
        position = max(0, end - overlap)
    return chunks


def ingest_document(document: Document) -> Document:
    """
    Initial ingestion: extract text + clean + previews.
    Parsing/LLM/chunking happen later via parse_document_range.
    """
    chunk_size = getattr(settings, "DOCUMENT_CHUNK_SIZE", 1000)
    overlap = getattr(settings, "DOCUMENT_CHUNK_OVERLAP", 100)
    logger.info("Ingesting document %s", document.id)

    document.status = DocumentStatus.PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message"])

    try:
        raw_pages = extract_pdf_pages(document.file.path)
        clean_pages = clean_page_texts(raw_pages)
        previews = render_page_previews(document)

        document.page_count = len(raw_pages)
        document.selected_page_start = 1 if raw_pages else None
        document.selected_page_end = len(raw_pages) if raw_pages else None

        with transaction.atomic():
            _persist_pages(document, raw_pages, clean_pages, previews)
            if not any(page.strip() for page in clean_pages):
                document.status = DocumentStatus.SCANNED_OR_EMPTY
                document.parse_status = ProcessingStatus.FAILED
                document.error_message = "No extractable text (scanned or empty)."
            else:
                document.status = DocumentStatus.COMPLETED
                document.parse_status = ProcessingStatus.NOT_STARTED

            document.processed_at = timezone.now()
            document.save(
                update_fields=[
                    "status",
                    "page_count",
                    "selected_page_start",
                    "selected_page_end",
                    "processed_at",
                    "parse_status",
                    "error_message",
                ]
            )

        # Legacy chunking for backward compatibility (optional)
        if clean_pages and any(clean_pages):
            chunks = chunk_text_with_overlap("\n\n".join(clean_pages), chunk_size, overlap)
            DocumentChunk.objects.filter(document=document).delete()
            objs = []
            for idx, text in enumerate(chunks):
                objs.append(
                    DocumentChunk(
                        document=document,
                        chunk_index=idx,
                        page_start=1,
                        page_end=len(clean_pages),
                        text=text,
                        metadata={"legacy": True},
                    )
                )
            if objs:
                DocumentChunk.objects.bulk_create(objs)
        return document
    except Exception as exc:
        logger.exception("Document ingestion failed: %s", exc)
        document.mark_failed(str(exc))
        return document


def parse_document_range(
    document: Document,
    page_start: int,
    page_end: int,
    mode: str = "hybrid",
    force_reparse: bool = False,
) -> Dict[str, Any]:
    """Structured parse for selected page range, creating Article + ArticleChunk."""
    if document.parse_status == ProcessingStatus.COMPLETED and not force_reparse:
        return {
            "parse_status": document.parse_status,
            "article_count": document.articles.count(),
            "warnings": ["parse skipped (already completed)"],
        }

    if page_start < 1 or page_end < page_start:
        raise ValueError("Invalid page range")
    if page_end > document.page_count:
        raise ValueError("page_end exceeds document page count")

    document.parse_status = ProcessingStatus.PROCESSING
    document.save(update_fields=["parse_status", "selected_page_start", "selected_page_end"])

    pages_qs = (
        DocumentPage.objects.filter(document=document, page_number__gte=page_start, page_number__lte=page_end)
        .order_by("page_number")
    )
    pages_payload = [(p.page_number, p.text_clean or p.text_raw or "") for p in pages_qs]
    regex_payload = regex_structure_pages(pages_payload)

    llm_payload: Optional[DocumentParsePayload] = None
    if mode in ("hybrid", "llm"):
        combined_text = "\n\n".join(text for _, text in pages_payload)
        llm_payload = refine_with_llm(combined_text, regex_payload)

    final_payload = llm_payload or regex_payload

    chunk_size = getattr(settings, "DOCUMENT_CHUNK_SIZE", 1000)
    overlap = getattr(settings, "DOCUMENT_CHUNK_OVERLAP", 100)

    try:
        with transaction.atomic():
            document.articles.all().delete()
            created_articles: List[Article] = []
            seen_keys = set()

            for idx, art in enumerate(final_payload.articles):
                if art.article_key in seen_keys:
                    logger.warning("Duplicate article_key detected, skipping: %s", art.article_key)
                    continue
                seen_keys.add(art.article_key)

                article = Article.objects.create(
                    document=document,
                    article_key=art.article_key,
                    title_in_parens=(art.title or ""),
                    full_title=art.full_title,
                    content=art.content,
                    chapter_title=art.chapter_title or "",
                    section_title=art.section_title or "",
                    order=idx,
                    source_pages=art.source_pages or [],
                    metadata={"warnings": art.warnings},
                )
                created_articles.append(article)

                chunks = chunk_text_with_overlap(art.content, chunk_size, overlap)
                chunk_objs = []
                for c_idx, chunk_text in enumerate(chunks):
                    chunk_objs.append(
                        ArticleChunk(
                            article=article,
                            chunk_index=c_idx,
                            chunk_text=chunk_text,
                            metadata={
                                "document_id": document.id,
                                "article_key": art.article_key,
                                "chapter_title": art.chapter_title,
                                "section_title": art.section_title,
                                "source_pages": art.source_pages,
                            },
                        )
                    )
                if chunk_objs:
                    ArticleChunk.objects.bulk_create(chunk_objs)

            document.selected_page_start = page_start
            document.selected_page_end = page_end
            document.parse_status = ProcessingStatus.COMPLETED
            document.upsert_status = ProcessingStatus.NOT_STARTED
            document.question_gen_status = ProcessingStatus.NOT_STARTED
            document.save(
                update_fields=[
                    "selected_page_start",
                    "selected_page_end",
                    "parse_status",
                    "upsert_status",
                    "question_gen_status",
                ]
            )

        warnings = list(final_payload.global_warnings)
        return {
            "parse_status": document.parse_status,
            "article_count": len(seen_keys),
            "warnings": warnings,
        }
    except Exception as exc:
        logger.exception("parse_document_range failed: %s", exc)
        document.parse_status = ProcessingStatus.FAILED
        document.save(update_fields=["parse_status"])
        raise


def maybe_embed_and_upsert(document: Document, article_chunks: Iterable[ArticleChunk]) -> Dict[str, Any]:
    """
    Embed ArticleChunks and upsert to vector DB (Chroma).
    """
    provider = getattr(settings, "EMBEDDING_PROVIDER", "none")
    vector_provider = getattr(settings, "VECTOR_DB_PROVIDER", "none")
    summary = {
        "provider": provider,
        "vector_provider": vector_provider,
        "processed_chunks": 0,
        "skipped": False,
    }
    if provider == "none" or vector_provider == "none":
        logger.info("Embedding/vector DB disabled (provider=%s, vector=%s)", provider, vector_provider)
        summary["skipped"] = True
        return summary

    if vector_provider != "chroma":
        summary["error"] = f"Unsupported vector provider: {vector_provider}"
        return summary

    try:
        collection = _get_chroma_collection()
        model = _get_embedder()
    except Exception as exc:
        summary["error"] = str(exc)
        return summary

    ids: List[str] = []
    embeddings: List[List[float]] = []
    metadatas: List[Dict[str, Any]] = []
    documents: List[str] = []
    for chunk in article_chunks:
        embedding = model.encode(chunk.chunk_text)
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        ids.append(f"{chunk.article.document_id}-{chunk.article_id}-{chunk.chunk_index}")
        metadatas.append(
            {
                "document_id": chunk.article.document_id,
                "article_id": chunk.article_id,
                "article_key": chunk.article.article_key,
                "chapter_title": chunk.article.chapter_title,
                "section_title": chunk.article.section_title,
                "source_pages": chunk.article.source_pages,
                "chunk_index": chunk.chunk_index,
            }
        )
        embeddings.append(embedding)  # type: ignore[arg-type]
        documents.append(chunk.chunk_text)

    if ids:
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
    summary["processed_chunks"] = len(ids)
    return summary


def upsert_document(document: Document) -> Dict[str, Any]:
    """Public wrapper for upsert endpoint."""
    document.upsert_status = ProcessingStatus.PROCESSING
    document.save(update_fields=["upsert_status"])

    try:
        chunks = ArticleChunk.objects.filter(article__document=document).order_by("article", "chunk_index")
        summary = maybe_embed_and_upsert(document, chunks)
        if summary.get("error"):
            document.upsert_status = ProcessingStatus.FAILED
            document.error_message = summary.get("error", "")
            document.save(update_fields=["upsert_status", "error_message"])
        else:
            document.upsert_status = ProcessingStatus.COMPLETED
            document.save(update_fields=["upsert_status"])
        return summary
    except Exception as exc:
        logger.exception("Upsert failed: %s", exc)
        document.upsert_status = ProcessingStatus.FAILED
        document.save(update_fields=["upsert_status"])
        return {"error": str(exc)}


@lru_cache(maxsize=1)
def _get_embedder() -> Any:
    """
    Lazy-load SentenceTransformer to avoid torch import at Django startup.
    Raises RuntimeError with a helpful message if torch/driver is missing.
    """
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:
        raise RuntimeError("SentenceTransformer import failed - verify torch dependency.") from exc

    model_name = getattr(settings, "EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    try:
        return SentenceTransformer(model_name)
    except OSError as exc:
        # Torch DLL/driver 문제 ???내
        raise RuntimeError(
            "Embedding model load failed: confirm torch/CUDA compatibility and drivers."
        ) from exc


@lru_cache(maxsize=1)
def _get_chroma_collection():
    url = getattr(settings, "CHROMA_URL", "")
    if not url:
        raise RuntimeError("CHROMA_URL is not configured.")
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 8000)
    if not host:
        raise RuntimeError("Invalid CHROMA_URL value.")
    ssl = parsed.scheme == "https"
    client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
    collection_name = getattr(settings, "CHROMA_COLLECTION", "documents")
    return client.get_or_create_collection(name=collection_name)


def search_similar_chunks(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    provider = getattr(settings, "VECTOR_DB_PROVIDER", "none")
    if provider != "chroma":
        return _fallback_db_search(query, top_k=top_k)
    try:
        model = _get_embedder()
        collection = _get_chroma_collection()
    except Exception as exc:
        logger.warning("search_similar_chunks disabled: %s", exc)
        return _fallback_db_search(query, top_k=top_k)
    vector = model.encode(query)
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    else:
        vector = list(vector)
    res = collection.query(query_embeddings=[vector], n_results=top_k)
    ids = (res.get("ids") or [[]])[0] if res else []
    metadatas = (res.get("metadatas") or [[]])[0] if res else []
    distances = (res.get("distances") or [[]])[0] if res else []
    results: List[Dict[str, Any]] = []
    for idx, payload in enumerate(metadatas):
        payload = payload or {}
        results.append(
            {
                "score": distances[idx] if idx < len(distances) else 0.0,
                "chunk_index": payload.get("chunk_index"),
                "article_key": payload.get("article_key"),
                "chapter_title": payload.get("chapter_title"),
                "section_title": payload.get("section_title"),
                "source_pages": payload.get("source_pages"),
                "document_id": payload.get("document_id"),
                "vector_id": ids[idx] if idx < len(ids) else "",
            }
        )
    if results:
        return results
    return _fallback_db_search(query, top_k=top_k)


def _fallback_db_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Lightweight fallback when vector DB/embedding is unavailable:
    naive icontains search over ArticleChunk text and article_key.
    """
    qs = ArticleChunk.objects.select_related("article").filter(
        models.Q(chunk_text__icontains=query) | models.Q(article__article_key__icontains=query)
    ).order_by("article__id", "chunk_index")[:max(1, top_k)]
    results: List[Dict[str, Any]] = []
    for ch in qs:
        results.append(
            {
                "score": 0.0,
                "chunk_index": ch.chunk_index,
                "article_key": ch.article.article_key,
                "chapter_title": ch.article.chapter_title,
                "section_title": ch.article.section_title,
                "source_pages": ch.article.source_pages,
                "document_id": ch.article.document_id,
                "vector_id": "",
            }
        )
    return results


def rag_answer(query: str, top_k: int = 5) -> Dict[str, Any]:
    chunks = search_similar_chunks(query, top_k=top_k)
    if not chunks:
        # ASCII message to avoid mojibake if encoding is misinterpreted downstream
        return {"answer": "No vector DB connected or no results.", "context": []}

    # Pull full chunk texts for context
    chunk_ids = []
    for item in chunks:
        if item.get("document_id") is None:
            continue
        chunk_ids.append((item["document_id"], item.get("chunk_index")))
    context_texts: List[str] = []
    if chunk_ids:
        qs = ArticleChunk.objects.filter(
            chunk_index__in=[c[1] for c in chunk_ids],
            article__document_id__in=[c[0] for c in chunk_ids],
        )
        for ch in qs:
            context_texts.append(f"[{ch.article.article_key}] {ch.chunk_text}")

    if getattr(settings, "LLM_PROVIDER", "none") == "none":
        return {
            "answer": "LLM disabled; review the context below.",
            "context": context_texts,
        }

    system_prompt = (
        "You are given snippets from legal/structured documents. "
        "Answer concisely using only this context. "
        "If the context is insufficient, say so explicitly."
    )
    user_prompt = json.dumps({"question": query, "context": context_texts}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        raw = _call_openai_compatible(messages)
        return {"answer": raw or "", "context": context_texts}
    except Exception as exc:
        logger.warning("RAG LLM call failed: %s", exc)
        return {"answer": "LLM call failed", "context": context_texts}


def _fallback_question_from_article(article: Article) -> str:
    """Simple rule-based question generator if LLM is disabled."""
    title = article.title_in_parens or article.full_title or article.article_key
    return f"What is the main point of {title}?"


def generate_questions(
    document: Document,
    per_article: int = 3,
    scope: str = "document",
    article_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    document.question_gen_status = ProcessingStatus.PROCESSING
    document.save(update_fields=["question_gen_status"])

    questions_created = 0
    try:
        target_articles = document.articles.all()
        if scope == "article" and article_ids:
            target_articles = target_articles.filter(id__in=article_ids)

        provider = getattr(settings, "LLM_PROVIDER", "openai_compat")
        use_llm = provider != "none"

        for article in target_articles:
            generated: List[str] = []
            if use_llm:
                try:
                    prompt = (
                        "Create a short list of comprehension questions for the provided article content. "
                        "Return JSON with an array field 'questions'."
                    )
                    messages = [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": article.content[:4000]},
                    ]
                    raw = _call_openai_compatible(messages)
                    if raw:
                        parsed = _extract_json_block(raw)
                        payload = json.loads(parsed)
                        if isinstance(payload, dict) and "questions" in payload:
                            payload = payload["questions"]
                        if isinstance(payload, list):
                            generated = [str(q) for q in payload][:per_article]
                except Exception as exc:
                    logger.warning("LLM question generation failed for article %s: %s", article.id, exc)

            if not generated:
                generated = [_fallback_question_from_article(article) for _ in range(per_article)]

            objs = []
            for q in generated:
                objs.append(
                    GeneratedQuestion(
                        document=document,
                        article=article if scope == "article" else None,
                        question_text=q,
                        expected_answer_snippet="",
                    )
                )
            if objs:
                GeneratedQuestion.objects.bulk_create(objs)
                questions_created += len(objs)

        document.question_gen_status = ProcessingStatus.COMPLETED
        document.save(update_fields=["question_gen_status"])
        return {"created": questions_created}
    except Exception as exc:
        logger.exception("Question generation failed: %s", exc)
        document.question_gen_status = ProcessingStatus.FAILED
        document.save(update_fields=["question_gen_status"])
        return {"error": str(exc)}
