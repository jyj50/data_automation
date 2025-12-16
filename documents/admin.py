from django.contrib import admin

from .models import (
    Article,
    ArticleChunk,
    Document,
    DocumentChunk,
    DocumentPage,
    GeneratedQuestion,
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "status",
        "parse_status",
        "upsert_status",
        "question_gen_status",
        "page_count",
        "created_at",
        "processed_at",
    )
    list_filter = ("status", "parse_status", "upsert_status", "question_gen_status", "created_at")
    search_fields = ("original_filename", "checksum")
    readonly_fields = ("created_at", "processed_at")


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "page_number")
    list_filter = ("document",)
    search_fields = ("document__original_filename",)


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "chunk_index", "page_start", "page_end")
    list_filter = ("document",)
    search_fields = ("document__original_filename", "metadata")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "article_key",
        "full_title",
        "chapter_title",
        "section_title",
        "order",
        "user_edited",
    )
    list_filter = ("document", "user_edited")
    search_fields = ("article_key", "full_title", "content")


@admin.register(ArticleChunk)
class ArticleChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "chunk_index")
    list_filter = ("article__document",)
    search_fields = ("article__article_key", "chunk_text")


@admin.register(GeneratedQuestion)
class GeneratedQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "article", "question_text", "created_at")
    list_filter = ("document",)
    search_fields = ("question_text",)
