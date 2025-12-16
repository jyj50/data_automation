import json
import os

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Article, ArticleChunk, Document, DocumentPage
from .services import (
    compute_checksum,
    generate_questions,
    ingest_document,
    parse_document_range,
    rag_answer,
    upsert_document,
)


def _serialize_document(document: Document, include_articles: bool = False) -> dict:
    data = {
        "id": document.id,
        "original_filename": document.original_filename,
        "status": document.status,
        "page_count": document.page_count,
        "selected_page_start": document.selected_page_start,
        "selected_page_end": document.selected_page_end,
        "parse_status": document.parse_status,
        "upsert_status": document.upsert_status,
        "question_gen_status": document.question_gen_status,
        "created_at": document.created_at.isoformat(),
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
        "error_message": document.error_message,
        "metadata": document.metadata,
    }
    if include_articles:
        data["articles"] = [
            {
                "id": art.id,
                "article_key": art.article_key,
                "full_title": art.full_title,
                "content": art.content,
                "chapter_title": art.chapter_title,
                "section_title": art.section_title,
                "source_pages": art.source_pages,
            }
            for art in document.articles.order_by("order")
        ]
    return data


def _parse_body(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST or {}


def home(request):
    """Wizard-style landing page."""
    documents = Document.objects.order_by("-created_at")[:50]
    if request.method == "POST":
        upload = request.FILES.get("file")
        if not upload:
            messages.error(request, "PDF 파일을 선택해주세요.")
            return redirect("documents:home")
        if not upload.name.lower().endswith(".pdf"):
            messages.error(request, "PDF만 업로드할 수 있습니다.")
            return redirect("documents:home")

        checksum = compute_checksum(upload)
        upload.seek(0)
        document = Document.objects.create(
            original_filename=upload.name,
            file=upload,
            checksum=checksum,
        )
        ingest_document(document)
        messages.success(request, f"{upload.name} 업로드 및 페이지 추출 완료")
        return redirect("documents:detail_page", document_id=document.id)

    return render(
        request,
        "documents/home.html",
        {
            "documents": documents,
        },
    )


def index(request):
    documents = Document.objects.order_by("-created_at")[:50]
    return JsonResponse(
        {
            "message": "Document ingestion API ready.",
            "documents": [
                {
                    "id": doc.id,
                    "original_filename": doc.original_filename,
                    "status": doc.status,
                    "page_count": doc.page_count,
                    "parse_status": doc.parse_status,
                }
                for doc in documents
            ],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def upload_document(request):
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "Missing file field 'file'."}, status=400)
    if not upload.name.lower().endswith(".pdf"):
        return JsonResponse({"error": "Only PDF uploads are supported."}, status=400)

    checksum = compute_checksum(upload)
    upload.seek(0)

    document = Document.objects.create(
        original_filename=upload.name,
        file=upload,
        checksum=checksum,
    )
    ingest_document(document)

    return JsonResponse(_serialize_document(document), status=201)


def document_detail(request, document_id: int):
    document = get_object_or_404(Document, id=document_id)
    return JsonResponse(_serialize_document(document, include_articles=True))


def document_pages(request, document_id: int):
    document = get_object_or_404(Document, id=document_id)
    pages = document.pages.order_by("page_number")
    return JsonResponse(
        {
            "document_id": document.id,
            "pages": [
                {
                    "page_number": page.page_number,
                    "has_text": bool((page.text_clean or page.text_raw).strip()),
                    "preview_url": page.preview_url,
                    "text_clean": (page.text_clean or "")[:500],
                }
                for page in pages
            ],
        }
    )


def document_page_preview(request, document_id: int, page_no: int):
    document = get_object_or_404(Document, id=document_id)
    page = get_object_or_404(DocumentPage, document=document, page_number=page_no)
    if not page.preview_image_path:
        return HttpResponseBadRequest("Preview not available.")
    abs_path = os.path.join(settings.MEDIA_ROOT, page.preview_image_path)
    if not os.path.exists(abs_path):
        return HttpResponseBadRequest("Preview file missing.")
    return FileResponse(open(abs_path, "rb"), content_type="image/png")


@csrf_exempt
@require_http_methods(["POST"])
def parse_document_view(request, document_id: int):
    document = get_object_or_404(Document, id=document_id)
    payload = _parse_body(request)
    page_start = int(payload.get("page_start") or 1)
    page_end = int(payload.get("page_end") or document.page_count)
    mode = payload.get("mode") or "hybrid"
    force_reparse = bool(payload.get("force_reparse"))
    try:
        result = parse_document_range(document, page_start, page_end, mode=mode, force_reparse=force_reparse)
        return JsonResponse(result)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
@require_http_methods(["PUT"])
def update_article(request, article_id: int):
    article = get_object_or_404(Article, id=article_id)
    payload = _parse_body(request)
    article.full_title = payload.get("full_title", article.full_title)
    article.content = payload.get("content", article.content)
    article.chapter_title = payload.get("chapter_title", article.chapter_title)
    article.section_title = payload.get("section_title", article.section_title)
    article.order = int(payload.get("order", article.order))
    article.user_edited = True
    article.version += 1
    article.save()
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_http_methods(["POST"])
def upsert_view(request, document_id: int):
    document = get_object_or_404(Document, id=document_id)
    summary = upsert_document(document)
    return JsonResponse(summary)


@csrf_exempt
@require_http_methods(["POST"])
def generate_questions_view(request, document_id: int):
    document = get_object_or_404(Document, id=document_id)
    payload = _parse_body(request)
    per_article = int(payload.get("per_article") or 3)
    scope = payload.get("scope") or "document"
    article_ids = payload.get("article_ids")
    if article_ids and isinstance(article_ids, str):
        try:
            article_ids = json.loads(article_ids)
        except json.JSONDecodeError:
            article_ids = []
    result = generate_questions(document, per_article=per_article, scope=scope, article_ids=article_ids)
    return JsonResponse(result)


def document_detail_page(request, document_id: int):
    document = get_object_or_404(Document, id=document_id)
    return render(
        request,
        "documents/detail.html",
        {
            "document": document,
            "articles": document.articles.order_by("order"),
            "pages": document.pages.order_by("page_number"),
            "questions": document.questions.all(),
        },
    )


def manage_documents(request):
    documents = Document.objects.order_by("-created_at")[:100]
    return render(
        request,
        "documents/manage.html",
        {"documents": documents},
    )


def manage_document_detail(request, document_id: int):
    document = get_object_or_404(Document, id=document_id)
    return render(
        request,
        "documents/manage_detail.html",
        {
            "document": document,
            "articles": document.articles.order_by("order"),
            "chunks": ArticleChunk.objects.filter(article__document=document).order_by("article", "chunk_index"),
            "questions": document.questions.order_by("-created_at"),
        },
    )


def chat_page(request):
    return render(request, "documents/chat.html")


@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    payload = _parse_body(request)
    query = payload.get("query", "")
    top_k = int(payload.get("top_k") or 5)
    if not query:
        return JsonResponse({"error": "query is required"}, status=400)
    result = rag_answer(query, top_k=top_k)
    return JsonResponse(result)
