from django.db import models
from django.contrib.auth.models import User


class ImageData(models.Model):
    """이미지 데이터 및 세그먼트 정보를 저장하는 모델"""
    title = models.CharField(max_length=200, verbose_name="제목")
    image_file = models.ImageField(upload_to='images/', verbose_name="이미지 파일")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 시간")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "이미지 데이터"
        verbose_name_plural = "이미지 데이터"


class ImageSegment(models.Model):
    """이미지 세그먼트 정보를 저장하는 모델"""
    image_data = models.ForeignKey(ImageData, on_delete=models.CASCADE, related_name='segments')
    label = models.CharField(max_length=100, verbose_name="객체 라벨 (음식 종류)")
    coordinates = models.JSONField(verbose_name="세그먼트 좌표 정보")  # [{x: int, y: int}, ...]
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.image_data.title} - {self.label}"

    class Meta:
        verbose_name = "이미지 세그먼트"
        verbose_name_plural = "이미지 세그먼트"


class TextData(models.Model):
    """텍스트 데이터 및 분석 결과를 저장하는 모델"""
    title = models.CharField(max_length=200, verbose_name="제목")
    original_text = models.TextField(verbose_name="원본 텍스트")
    processed_text = models.TextField(blank=True, verbose_name="처리된 텍스트")
    morphemes = models.JSONField(default=list, verbose_name="형태소 분석 결과")  # [{"word": str, "pos": str}, ...]
    keywords = models.JSONField(default=list, verbose_name="키워드 추출 결과")  # [str, ...]
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "텍스트 데이터"
        verbose_name_plural = "텍스트 데이터"


class AudioData(models.Model):
    """음성 데이터 및 변환 결과를 저장하는 모델"""
    title = models.CharField(max_length=200, verbose_name="제목")
    audio_file = models.FileField(upload_to='audio/', verbose_name="음성 파일")
    transcribed_text = models.TextField(blank=True, verbose_name="변환된 텍스트")
    extracted_keywords = models.JSONField(default=list, verbose_name="추출된 키워드")  # [str, ...]
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '처리 대기'),
            ('processing', '처리 중'),
            ('completed', '완료'),
            ('error', '오류')
        ],
        default='pending',
        verbose_name="처리 상태"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "음성 데이터"
        verbose_name_plural = "음성 데이터"


class ProcessingLog(models.Model):
    """데이터 처리 로그를 저장하는 모델"""
    content_type = models.CharField(
        max_length=20,
        choices=[
            ('image', '이미지'),
            ('text', '텍스트'),
            ('audio', '음성')
        ],
        verbose_name="데이터 타입"
    )
    object_id = models.PositiveIntegerField(verbose_name="객체 ID")
    process_type = models.CharField(max_length=50, verbose_name="처리 타입")
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', '성공'),
            ('error', '실패')
        ],
        verbose_name="처리 결과"
    )
    message = models.TextField(blank=True, verbose_name="처리 메시지")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.content_type} - {self.process_type} - {self.status}"

    class Meta:
        verbose_name = "처리 로그"
        verbose_name_plural = "처리 로그"
        ordering = ['-created_at']
