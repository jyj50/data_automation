from django.contrib import admin
from .models import ImageData, ImageSegment, TextData, AudioData, ProcessingLog


@admin.register(ImageData)
class ImageDataAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['title']
    readonly_fields = ['uploaded_at']
    ordering = ['-uploaded_at']


@admin.register(ImageSegment)
class ImageSegmentAdmin(admin.ModelAdmin):
    list_display = ['image_data', 'label', 'created_at']
    list_filter = ['created_at', 'label']
    search_fields = ['label', 'image_data__title']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(TextData)
class TextDataAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'original_text']
    readonly_fields = ['created_at', 'processed_text', 'morphemes', 'keywords']
    ordering = ['-created_at']

    def get_readonly_fields(self, request, obj=None):
        # 편집 시에만 처리된 데이터를 읽기 전용으로 설정
        if obj:  # 기존 객체 편집 시
            return self.readonly_fields
        return ['created_at']  # 새 객체 생성 시


@admin.register(AudioData)
class AudioDataAdmin(admin.ModelAdmin):
    list_display = ['title', 'processing_status', 'user', 'uploaded_at', 'processed_at']
    list_filter = ['processing_status', 'uploaded_at', 'processed_at']
    search_fields = ['title', 'transcribed_text']
    readonly_fields = ['uploaded_at', 'processed_at', 'transcribed_text', 'extracted_keywords']
    ordering = ['-uploaded_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # 기존 객체 편집 시
            return self.readonly_fields
        return ['uploaded_at']  # 새 객체 생성 시


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    list_display = ['content_type', 'process_type', 'status', 'created_at']
    list_filter = ['content_type', 'process_type', 'status', 'created_at']
    search_fields = ['message']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False  # 로그는 수동 생성 불가

    def has_change_permission(self, request, obj=None):
        return False  # 로그는 수정 불가
