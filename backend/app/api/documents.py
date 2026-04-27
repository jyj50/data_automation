import hashlib
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.deps import get_db
from app.models.db import Document, DocumentPage
from app.schemas.documents import (
    DocumentOut,
    DocumentPageOut,
    GenerateQuestionsRequest,
    PagesResponse,
    ParseRequest,
    ParseResponse,
)
from app.services.pdf import (
    generate_questions,
    ingest_document,
    parse_document_range,
    upsert_document,
)

router = APIRouter(tags=["documents"])


@router.post("/documents/upload/", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF uploads are supported.")

    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()

    rel_dir = "documents"
    abs_dir = os.path.join(settings.media_root, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    safe_name = (file.filename or "upload.pdf").replace(" ", "_")
    filename = f"{checksum[:8]}_{safe_name}"
    rel_path = f"{rel_dir}/{filename}"
    abs_path = os.path.join(settings.media_root, rel_path)
    with open(abs_path, "wb") as f:
        f.write(content)

    document = Document(
        original_filename=file.filename or safe_name,
        file_path=rel_path,
        checksum=checksum,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    ingest_document(db, document, settings)
    db.refresh(document)
    return document


@router.get("/documents/", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).limit(50).all()


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = (
        db.query(Document)
        .options(selectinload(Document.articles))
        .filter(Document.id == document_id)
        .first()
    )
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


@router.get("/documents/{document_id}/pages/", response_model=PagesResponse)
def document_pages(document_id: int, db: Session = Depends(get_db)):
    if not db.get(Document, document_id):
        raise HTTPException(404, "Document not found.")
    pages = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
        .all()
    )
    return PagesResponse(
        document_id=document_id,
        pages=[
            DocumentPageOut(
                page_number=p.page_number,
                has_text=bool((p.text_clean or p.text_raw or "").strip()),
                preview_url=p.preview_url,
                text_clean=(p.text_clean or "")[:500],
            )
            for p in pages
        ],
    )


@router.get("/documents/{document_id}/pages/{page_no}/preview/")
def document_page_preview(
    document_id: int,
    page_no: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not db.get(Document, document_id):
        raise HTTPException(404, "Document not found.")
    page = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id, DocumentPage.page_number == page_no)
        .first()
    )
    if not page or not page.preview_image_path:
        raise HTTPException(404, "Preview not available.")
    abs_path = os.path.join(settings.media_root, page.preview_image_path)
    if not os.path.exists(abs_path):
        raise HTTPException(404, "Preview file missing.")
    return FileResponse(abs_path, media_type="image/png")


@router.post("/documents/{document_id}/parse/", response_model=ParseResponse)
def parse_document(
    document_id: int,
    body: ParseRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    page_end = body.page_end or doc.page_count
    try:
        result = parse_document_range(
            db, doc, body.page_start, page_end,
            mode=body.mode, force_reparse=body.force_reparse, settings=settings,
        )
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/documents/{document_id}/upsert/")
def upsert_document_view(
    document_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return upsert_document(db, doc, settings)


@router.post("/documents/{document_id}/generate-questions/")
def generate_questions_view(
    document_id: int,
    body: GenerateQuestionsRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return generate_questions(
        db, doc,
        per_article=body.per_article,
        scope=body.scope,
        article_ids=body.article_ids,
        settings=settings,
    )
