from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------- Response schemas ----------

class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_key: str
    full_title: str
    content: str
    chapter_title: str
    section_title: str
    source_pages: List[int]
    order: int
    user_edited: bool


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    status: str
    page_count: int
    selected_page_start: Optional[int]
    selected_page_end: Optional[int]
    parse_status: str
    upsert_status: str
    question_gen_status: str
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: str
    articles: Optional[List[ArticleOut]] = None


class DocumentPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    has_text: bool
    preview_url: str
    text_clean: str


class PagesResponse(BaseModel):
    document_id: int
    pages: List[DocumentPageOut]


class ParseResponse(BaseModel):
    parse_status: str
    article_count: int
    warnings: List[str]


class ChatResponse(BaseModel):
    answer: str
    context: List[str]


# ---------- Request schemas ----------

class ParseRequest(BaseModel):
    page_start: int = 1
    page_end: int = 0  # 0 = use document.page_count
    mode: str = "hybrid"
    force_reparse: bool = False


class ArticleUpdateRequest(BaseModel):
    full_title: Optional[str] = None
    content: Optional[str] = None
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None
    order: Optional[int] = None


class GenerateQuestionsRequest(BaseModel):
    per_article: int = 3
    scope: str = "document"
    article_ids: Optional[List[int]] = None


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5
