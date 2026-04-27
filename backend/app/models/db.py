import enum
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SCANNED_OR_EMPTY = "scanned_or_empty"
    FAILED = "failed"


class ProcessingStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default=DocumentStatus.UPLOADED)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    selected_page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    selected_page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), default=ProcessingStatus.NOT_STARTED)
    upsert_status: Mapped[str] = mapped_column(String(32), default=ProcessingStatus.NOT_STARTED)
    question_gen_status: Mapped[str] = mapped_column(String(32), default=ProcessingStatus.NOT_STARTED)
    error_message: Mapped[str] = mapped_column(Text, default="")
    # mapped as "metadata" in DB; use metadata_ in Python to avoid conflict with SQLAlchemy Base.metadata
    metadata_: Mapped[Dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    pages: Mapped[List["DocumentPage"]] = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan",
        order_by="DocumentPage.page_number",
    )
    articles: Mapped[List["Article"]] = relationship(
        "Article", back_populates="document", cascade="all, delete-orphan",
    )
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan",
    )
    questions: Mapped[List["GeneratedQuestion"]] = relationship(
        "GeneratedQuestion", back_populates="document", cascade="all, delete-orphan",
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    page_number: Mapped[int] = mapped_column(Integer)
    text_raw: Mapped[str] = mapped_column(Text, default="")
    text_clean: Mapped[str] = mapped_column(Text, default="")
    preview_image_path: Mapped[str] = mapped_column(String(255), default="")

    document: Mapped["Document"] = relationship("Document", back_populates="pages")

    @property
    def preview_url(self) -> str:
        if not self.preview_image_path:
            return ""
        return f"/media/{self.preview_image_path.lstrip('/')}"


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_id: Mapped[str] = mapped_column(String(255), default="")
    metadata_: Mapped[Dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    article_key: Mapped[str] = mapped_column(String(50), index=True)
    title_in_parens: Mapped[str] = mapped_column(String(255), default="")
    full_title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    chapter_title: Mapped[str] = mapped_column(String(255), default="")
    section_title: Mapped[str] = mapped_column(String(255), default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    source_pages: Mapped[List] = mapped_column(JSON, default=list)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_: Mapped[Dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document: Mapped["Document"] = relationship("Document", back_populates="articles")
    chunks: Mapped[List["ArticleChunk"]] = relationship(
        "ArticleChunk", back_populates="article", cascade="all, delete-orphan",
    )
    questions: Mapped[List["GeneratedQuestion"]] = relationship(
        "GeneratedQuestion", back_populates="article",
    )


class ArticleChunk(Base):
    __tablename__ = "article_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(Integer, ForeignKey("articles.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding_id: Mapped[str] = mapped_column(String(255), default="")
    vector_id: Mapped[str] = mapped_column(String(255), default="")
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[Dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    article: Mapped["Article"] = relationship("Article", back_populates="chunks")


class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    article_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    question_text: Mapped[str] = mapped_column(Text)
    expected_answer_snippet: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship("Document", back_populates="questions")
    article: Mapped[Optional["Article"]] = relationship("Article", back_populates="questions")
