"""
Core PDF processing and RAG preparation utilities.
Ported from Django documents/services.py → FastAPI + SQLAlchemy.

Pure logic (regex, chunking, PDF parsing, LLM calls) is unchanged.
DB access replaces Django ORM with SQLAlchemy Session.
settings.X references replaced with Settings object from app.core.config.
"""

import hashlib
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import chromadb
import fitz  # PyMuPDF
import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from app.core.config import Settings, get_settings
from app.models.db import (
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

CHAPTER_PATTERN = re.compile(r"^제\s*\d+\s*장\b.*")
SECTION_PATTERN = re.compile(r"^제\s*\d+\s*절\b.*")
ARTICLE_PATTERN = re.compile(r"^(제\s*\d+\s*조(?:의\s*\d+)?)(\s*\([^)]*\))?(.*)$")


# ---------- Pydantic parse payloads (unchanged from original) ----------

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


# ---------- Pure utilities (no DB, no settings dependency) ----------

def compute_checksum(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def extract_pdf_pages(file_path: str) -> List[str]:
    with fitz.open(file_path) as doc:
        return [page.get_text("text") or "" for page in doc]


def render_page_previews(document: Document, media_root: str) -> Dict[int, str]:
    previews: Dict[int, str] = {}
    output_root = os.path.join("documents", str(document.id), "pages")
    full_root = os.path.join(media_root, output_root)
    _ensure_dir(full_root)

    file_abs_path = os.path.join(media_root, document.file_path)
    with fitz.open(file_abs_path) as pdf:
        for idx, page in enumerate(pdf, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            filename = f"page_{idx:04d}.png"
            rel_path = os.path.join(output_root, filename)
            pix.save(os.path.join(full_root, filename))
            previews[idx] = rel_path.replace("\\", "/")
    return previews


def _strip_repeated_lines(pages: Sequence[str], min_ratio: float = 0.6) -> List[str]:
    if not pages:
        return []
    line_counts: Counter = Counter()
    page_lines: List[List[str]] = []
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        line_counts.update(set(lines))
        page_lines.append(lines)
    threshold = max(2, int(len(pages) * min_ratio))
    repeated = {line for line, count in line_counts.items() if count >= threshold}
    return ["\n".join(line for line in lines if line not in repeated) for lines in page_lines]


def clean_page_texts(pages: Sequence[str]) -> List[str]:
    repeated_stripped = _strip_repeated_lines(pages)
    cleaned = []
    for page in repeated_stripped:
        text = page.replace("﻿", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        cleaned.append(text.strip())
    return cleaned


def _normalize_content_lines(lines: Sequence[str]) -> str:
    normalized = []
    for line in lines:
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        if cleaned:
            normalized.append(cleaned)
    return "\n".join(normalized)


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


# ---------- Structured parsing (pure, no DB) ----------

def regex_structure_pages(pages: Sequence[Tuple[int, str]]) -> DocumentParsePayload:
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


# ---------- LLM utilities ----------

def _extract_json_block(text: str) -> str:
    if not text:
        raise ValueError("Empty LLM response")
    fence = re.search(r"\{.*\}", text, flags=re.S)
    if fence:
        return fence.group(0)
    return text


def _call_openai_compatible(
    messages: List[Dict[str, str]],
    settings: Optional[Settings] = None,
) -> Optional[str]:
    if settings is None:
        settings = get_settings()
    if settings.llm_provider == "none":
        return None
    if not settings.llm_base_url:
        logger.info("LLM base URL missing; skipping LLM call.")
        return None

    url = settings.llm_base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0,
        "top_p": 1,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("No choices returned from LLM")
        return choices[0].get("message", {}).get("content", "")


def refine_with_llm(
    base_text: str,
    regex_payload: DocumentParsePayload,
    settings: Optional[Settings] = None,
) -> Optional[DocumentParsePayload]:
    if settings is None:
        settings = get_settings()
    candidate_keys = {a.article_key for a in regex_payload.articles}
    user_payload = {
        "regex_candidates": [a.model_dump() for a in regex_payload.articles],
        "full_text": base_text[:20000],
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
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    attempts = 0
    last_error: Optional[Exception] = None
    while attempts < 2:
        try:
            raw = _call_openai_compatible(messages, settings)
            if raw is None:
                return None
            parsed = _extract_json_block(raw)
            payload = DocumentParsePayload(**json.loads(parsed))
            filtered = [a for a in payload.articles if a.article_key in candidate_keys]
            return DocumentParsePayload(articles=filtered, global_warnings=payload.global_warnings)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            attempts += 1
            last_error = exc
            messages.append({"role": "user", "content": "Schema mismatch. Return valid JSON."})
        except Exception as exc:
            logger.warning("LLM refinement failed: %s", exc)
            return None
    if last_error:
        logger.warning("LLM refinement failed after retry: %s", last_error)
    return None


# ---------- Cached singletons (embedding model, chroma client) ----------

@lru_cache(maxsize=1)
def _get_embedder() -> Any:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:
        raise RuntimeError("SentenceTransformer import failed - verify torch dependency.") from exc
    model_name = get_settings().embedding_model_name
    try:
        return SentenceTransformer(model_name)
    except OSError as exc:
        raise RuntimeError("Embedding model load failed: confirm torch/CUDA compatibility.") from exc


@lru_cache(maxsize=1)
def _get_chroma_collection():
    url = get_settings().chroma_url
    if not url:
        raise RuntimeError("CHROMA_URL is not configured.")
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 8000)
    if not host:
        raise RuntimeError("Invalid CHROMA_URL value.")
    ssl = parsed.scheme == "https"
    client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
    collection_name = get_settings().chroma_collection
    return client.get_or_create_collection(name=collection_name)


# ---------- DB-aware functions (require Session) ----------

def _persist_pages(
    db: Session,
    document: Document,
    raw_pages: Sequence[str],
    clean_pages: Sequence[str],
    previews: Optional[Dict[int, str]] = None,
) -> None:
    db.query(DocumentPage).filter(DocumentPage.document_id == document.id).delete()
    page_objs = []
    for idx, (raw, clean) in enumerate(zip(raw_pages, clean_pages), start=1):
        preview_path = previews.get(idx, "") if previews else ""
        page_objs.append(
            DocumentPage(
                document_id=document.id,
                page_number=idx,
                text_raw=raw,
                text_clean=clean,
                preview_image_path=preview_path,
            )
        )
    if page_objs:
        db.add_all(page_objs)
        db.flush()


def ingest_document(
    db: Session,
    document: Document,
    settings: Optional[Settings] = None,
) -> Document:
    if settings is None:
        settings = get_settings()
    chunk_size = settings.document_chunk_size
    overlap = settings.document_chunk_overlap
    logger.info("Ingesting document %s", document.id)

    document.status = DocumentStatus.PROCESSING
    document.error_message = ""
    db.commit()

    try:
        file_abs_path = os.path.join(settings.media_root, document.file_path)
        raw_pages = extract_pdf_pages(file_abs_path)
        clean_pages = clean_page_texts(raw_pages)
        previews = render_page_previews(document, settings.media_root)

        document.page_count = len(raw_pages)
        document.selected_page_start = 1 if raw_pages else None
        document.selected_page_end = len(raw_pages) if raw_pages else None

        _persist_pages(db, document, raw_pages, clean_pages, previews)

        if not any(page.strip() for page in clean_pages):
            document.status = DocumentStatus.SCANNED_OR_EMPTY
            document.parse_status = ProcessingStatus.FAILED
            document.error_message = "No extractable text (scanned or empty)."
        else:
            document.status = DocumentStatus.COMPLETED
            document.parse_status = ProcessingStatus.NOT_STARTED

        document.processed_at = datetime.utcnow()
        db.commit()

        # Legacy document-level chunking (kept for backward compatibility)
        if clean_pages and any(clean_pages):
            chunks = chunk_text_with_overlap("\n\n".join(clean_pages), chunk_size, overlap)
            db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
            objs = [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    page_start=1,
                    page_end=len(clean_pages),
                    text=text,
                    metadata_={"legacy": True},
                )
                for idx, text in enumerate(chunks)
            ]
            if objs:
                db.add_all(objs)
                db.commit()

        db.refresh(document)
        return document
    except Exception as exc:
        logger.exception("Document ingestion failed: %s", exc)
        db.rollback()
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)
        document.processed_at = datetime.utcnow()
        db.commit()
        return document


def parse_document_range(
    db: Session,
    document: Document,
    page_start: int,
    page_end: int,
    mode: str = "hybrid",
    force_reparse: bool = False,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    if settings is None:
        settings = get_settings()

    article_count = db.query(Article).filter(Article.document_id == document.id).count()
    if document.parse_status == ProcessingStatus.COMPLETED and not force_reparse:
        return {
            "parse_status": document.parse_status,
            "article_count": article_count,
            "warnings": ["parse skipped (already completed)"],
        }

    if page_start < 1 or page_end < page_start:
        raise ValueError("Invalid page range")
    if page_end > document.page_count:
        raise ValueError("page_end exceeds document page count")

    document.parse_status = ProcessingStatus.PROCESSING
    document.selected_page_start = page_start
    document.selected_page_end = page_end
    db.commit()

    pages_qs = (
        db.query(DocumentPage)
        .filter(
            DocumentPage.document_id == document.id,
            DocumentPage.page_number >= page_start,
            DocumentPage.page_number <= page_end,
        )
        .order_by(DocumentPage.page_number)
        .all()
    )
    pages_payload = [(p.page_number, p.text_clean or p.text_raw or "") for p in pages_qs]
    regex_payload = regex_structure_pages(pages_payload)

    llm_payload: Optional[DocumentParsePayload] = None
    if mode in ("hybrid", "llm"):
        combined_text = "\n\n".join(text for _, text in pages_payload)
        llm_payload = refine_with_llm(combined_text, regex_payload, settings)

    final_payload = llm_payload or regex_payload
    chunk_size = settings.document_chunk_size
    overlap = settings.document_chunk_overlap

    try:
        db.query(Article).filter(Article.document_id == document.id).delete(synchronize_session=False)
        db.flush()

        seen_keys: set = set()
        for idx, art in enumerate(final_payload.articles):
            if art.article_key in seen_keys:
                logger.warning("Duplicate article_key detected, skipping: %s", art.article_key)
                continue
            seen_keys.add(art.article_key)

            article = Article(
                document_id=document.id,
                article_key=art.article_key,
                title_in_parens=(art.title or ""),
                full_title=art.full_title,
                content=art.content,
                chapter_title=art.chapter_title or "",
                section_title=art.section_title or "",
                order=idx,
                source_pages=art.source_pages or [],
                metadata_={"warnings": art.warnings},
            )
            db.add(article)
            db.flush()  # get article.id before creating chunks

            chunk_texts = chunk_text_with_overlap(art.content, chunk_size, overlap)
            chunk_objs = [
                ArticleChunk(
                    article_id=article.id,
                    chunk_index=c_idx,
                    chunk_text=chunk_text,
                    metadata_={
                        "document_id": document.id,
                        "article_key": art.article_key,
                        "chapter_title": art.chapter_title,
                        "section_title": art.section_title,
                        "source_pages": art.source_pages,
                    },
                )
                for c_idx, chunk_text in enumerate(chunk_texts)
            ]
            if chunk_objs:
                db.add_all(chunk_objs)
                db.flush()

        document.selected_page_start = page_start
        document.selected_page_end = page_end
        document.parse_status = ProcessingStatus.COMPLETED
        document.upsert_status = ProcessingStatus.NOT_STARTED
        document.question_gen_status = ProcessingStatus.NOT_STARTED
        db.commit()

        return {
            "parse_status": document.parse_status,
            "article_count": len(seen_keys),
            "warnings": list(final_payload.global_warnings),
        }
    except Exception as exc:
        logger.exception("parse_document_range failed: %s", exc)
        db.rollback()
        document.parse_status = ProcessingStatus.FAILED
        db.commit()
        raise


def maybe_embed_and_upsert(
    document: Document,
    article_chunks: Iterable[ArticleChunk],
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    if settings is None:
        settings = get_settings()
    provider = settings.embedding_provider
    vector_provider = settings.vector_db_provider
    summary: Dict[str, Any] = {
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
        metadatas.append({
            "document_id": chunk.article.document_id,
            "article_id": chunk.article_id,
            "article_key": chunk.article.article_key,
            "chapter_title": chunk.article.chapter_title,
            "section_title": chunk.article.section_title,
            "source_pages": chunk.article.source_pages,
            "chunk_index": chunk.chunk_index,
        })
        embeddings.append(embedding)
        documents.append(chunk.chunk_text)

    if ids:
        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
    summary["processed_chunks"] = len(ids)
    return summary


def upsert_document(
    db: Session,
    document: Document,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    if settings is None:
        settings = get_settings()
    document.upsert_status = ProcessingStatus.PROCESSING
    db.commit()
    try:
        chunks = (
            db.query(ArticleChunk)
            .join(Article)
            .filter(Article.document_id == document.id)
            .options(joinedload(ArticleChunk.article))
            .order_by(Article.id, ArticleChunk.chunk_index)
            .all()
        )
        summary = maybe_embed_and_upsert(document, chunks, settings)
        if summary.get("error"):
            document.upsert_status = ProcessingStatus.FAILED
            document.error_message = summary.get("error", "")
        else:
            document.upsert_status = ProcessingStatus.COMPLETED
        db.commit()
        return summary
    except Exception as exc:
        logger.exception("Upsert failed: %s", exc)
        db.rollback()
        document.upsert_status = ProcessingStatus.FAILED
        db.commit()
        return {"error": str(exc)}


def _fallback_db_search(db: Session, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    qs = (
        db.query(ArticleChunk)
        .join(Article)
        .filter(
            or_(
                ArticleChunk.chunk_text.ilike(f"%{query}%"),
                Article.article_key.ilike(f"%{query}%"),
            )
        )
        .options(joinedload(ArticleChunk.article))
        .order_by(Article.id, ArticleChunk.chunk_index)
        .limit(max(1, top_k))
        .all()
    )
    return [
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
        for ch in qs
    ]


def search_similar_chunks(
    db: Session,
    query: str,
    top_k: int = 5,
    settings: Optional[Settings] = None,
) -> List[Dict[str, Any]]:
    if settings is None:
        settings = get_settings()
    if settings.vector_db_provider != "chroma":
        return _fallback_db_search(db, query, top_k=top_k)
    try:
        model = _get_embedder()
        collection = _get_chroma_collection()
    except Exception as exc:
        logger.warning("search_similar_chunks disabled: %s", exc)
        return _fallback_db_search(db, query, top_k=top_k)

    vector = model.encode(query)
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    else:
        vector = list(vector)

    res = collection.query(query_embeddings=[vector], n_results=top_k)
    ids = (res.get("ids") or [[]])[0] if res else []
    metas = (res.get("metadatas") or [[]])[0] if res else []
    distances = (res.get("distances") or [[]])[0] if res else []

    results = [
        {
            "score": distances[i] if i < len(distances) else 0.0,
            "chunk_index": (metas[i] or {}).get("chunk_index"),
            "article_key": (metas[i] or {}).get("article_key"),
            "chapter_title": (metas[i] or {}).get("chapter_title"),
            "section_title": (metas[i] or {}).get("section_title"),
            "source_pages": (metas[i] or {}).get("source_pages"),
            "document_id": (metas[i] or {}).get("document_id"),
            "vector_id": ids[i] if i < len(ids) else "",
        }
        for i in range(len(metas))
    ]
    if results:
        return results
    return _fallback_db_search(db, query, top_k=top_k)


def rag_answer(
    db: Session,
    query: str,
    top_k: int = 5,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    if settings is None:
        settings = get_settings()
    chunks = search_similar_chunks(db, query, top_k=top_k, settings=settings)
    if not chunks:
        return {"answer": "No vector DB connected or no results.", "context": []}

    doc_ids = [item["document_id"] for item in chunks if item.get("document_id") is not None]
    chunk_indices = [item["chunk_index"] for item in chunks if item.get("chunk_index") is not None]

    context_texts: List[str] = []
    if doc_ids and chunk_indices:
        qs = (
            db.query(ArticleChunk)
            .join(Article)
            .filter(
                ArticleChunk.chunk_index.in_(chunk_indices),
                Article.document_id.in_(doc_ids),
            )
            .options(joinedload(ArticleChunk.article))
            .all()
        )
        for ch in qs:
            context_texts.append(f"[{ch.article.article_key}] {ch.chunk_text}")

    if settings.llm_provider == "none":
        return {"answer": "LLM disabled; review the context below.", "context": context_texts}

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
        raw = _call_openai_compatible(messages, settings)
        return {"answer": raw or "", "context": context_texts}
    except Exception as exc:
        logger.warning("RAG LLM call failed: %s", exc)
        return {"answer": "LLM call failed", "context": context_texts}


def _fallback_question_from_article(article: Article) -> str:
    title = article.title_in_parens or article.full_title or article.article_key
    return f"What is the main point of {title}?"


def generate_questions(
    db: Session,
    document: Document,
    per_article: int = 3,
    scope: str = "document",
    article_ids: Optional[List[int]] = None,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    if settings is None:
        settings = get_settings()
    document.question_gen_status = ProcessingStatus.PROCESSING
    db.commit()

    questions_created = 0
    try:
        target_articles = db.query(Article).filter(Article.document_id == document.id)
        if scope == "article" and article_ids:
            target_articles = target_articles.filter(Article.id.in_(article_ids))
        target_articles = target_articles.all()

        use_llm = settings.llm_provider != "none"

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
                    raw = _call_openai_compatible(messages, settings)
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

            objs = [
                GeneratedQuestion(
                    document_id=document.id,
                    article_id=article.id if scope == "article" else None,
                    question_text=q,
                    expected_answer_snippet="",
                )
                for q in generated
            ]
            if objs:
                db.add_all(objs)
                questions_created += len(objs)

        db.commit()
        document.question_gen_status = ProcessingStatus.COMPLETED
        db.commit()
        return {"created": questions_created}
    except Exception as exc:
        logger.exception("Question generation failed: %s", exc)
        db.rollback()
        document.question_gen_status = ProcessingStatus.FAILED
        db.commit()
        return {"error": str(exc)}
