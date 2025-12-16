from django.db import models
from django.utils import timezone


class DocumentStatus(models.TextChoices):
    UPLOADED = "uploaded", "Uploaded"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    SCANNED_OR_EMPTY = "scanned_or_empty", "Scanned or Empty"
    FAILED = "failed", "Failed"


class ProcessingStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not Started"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class Document(models.Model):
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    checksum = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADED,
    )
    page_count = models.PositiveIntegerField(default=0)
    selected_page_start = models.PositiveIntegerField(null=True, blank=True)
    selected_page_end = models.PositiveIntegerField(null=True, blank=True)
    parse_status = models.CharField(
        max_length=32, choices=ProcessingStatus.choices, default=ProcessingStatus.NOT_STARTED
    )
    upsert_status = models.CharField(
        max_length=32, choices=ProcessingStatus.choices, default=ProcessingStatus.NOT_STARTED
    )
    question_gen_status = models.CharField(
        max_length=32, choices=ProcessingStatus.choices, default=ProcessingStatus.NOT_STARTED
    )
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.original_filename} ({self.status})"

    def mark_failed(self, message: str):
        """Convenience helper to persist failure state for ingestion."""
        self.status = DocumentStatus.FAILED
        self.error_message = message
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "error_message", "processed_at"])

    class Meta:
        ordering = ["-created_at"]


class DocumentPage(models.Model):
    document = models.ForeignKey(
        Document, related_name="pages", on_delete=models.CASCADE
    )
    page_number = models.PositiveIntegerField()
    text_raw = models.TextField(blank=True)
    text_clean = models.TextField(blank=True)
    preview_image_path = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["page_number"]
        unique_together = ("document", "page_number")

    def __str__(self):
        return f"{self.document_id} p.{self.page_number}"

    @property
    def preview_url(self):
        if not self.preview_image_path:
            return ""
        return f"/media/{self.preview_image_path.lstrip('/')}"


class DocumentChunk(models.Model):
    # Legacy chunking (pre-article). Kept for backward compatibility.
    document = models.ForeignKey(
        Document, related_name="chunks", on_delete=models.CASCADE
    )
    chunk_index = models.PositiveIntegerField()
    page_start = models.PositiveIntegerField()
    page_end = models.PositiveIntegerField()
    text = models.TextField()
    token_count = models.PositiveIntegerField(null=True, blank=True)
    embedding_id = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]
        unique_together = ("document", "chunk_index")

    def __str__(self):
        return f"Doc {self.document_id} chunk {self.chunk_index}"


class Article(models.Model):
    document = models.ForeignKey(
        Document, related_name="articles", on_delete=models.CASCADE
    )
    article_key = models.CharField(max_length=50, db_index=True)
    title_in_parens = models.CharField(max_length=255, blank=True)
    full_title = models.CharField(max_length=255)
    content = models.TextField()
    chapter_title = models.CharField(max_length=255, blank=True)
    section_title = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    source_pages = models.JSONField(default=list, blank=True)
    user_edited = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("document", "article_key")

    def __str__(self):
        return f"{self.article_key} - {self.full_title}"


class ArticleChunk(models.Model):
    article = models.ForeignKey(
        Article, related_name="chunks", on_delete=models.CASCADE
    )
    chunk_index = models.PositiveIntegerField()
    chunk_text = models.TextField()
    embedding_id = models.CharField(max_length=255, blank=True)
    vector_id = models.CharField(max_length=255, blank=True)
    token_count = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]
        unique_together = ("article", "chunk_index")

    def __str__(self):
        return f"{self.article.article_key} chunk {self.chunk_index}"


class GeneratedQuestion(models.Model):
    document = models.ForeignKey(
        Document, related_name="questions", on_delete=models.CASCADE
    )
    article = models.ForeignKey(
        Article, related_name="questions", null=True, blank=True, on_delete=models.SET_NULL
    )
    question_text = models.TextField()
    expected_answer_snippet = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Q for doc {self.document_id}: {self.question_text[:50]}..."
