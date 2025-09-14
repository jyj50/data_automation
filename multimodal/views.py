from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json
import os
from .models import ImageData, ImageSegment, TextData, AudioData, ProcessingLog
from .utils import process_text_with_kiwi, process_audio_with_whisper


def home(request):
    """메인 페이지 뷰"""
    context = {
        'recent_images': ImageData.objects.order_by('-uploaded_at')[:3],
        'recent_texts': TextData.objects.order_by('-created_at')[:3],
        'recent_audios': AudioData.objects.order_by('-uploaded_at')[:3],
    }
    return render(request, 'multimodal/home.html', context)


# ========== 이미지 처리 관련 뷰 ==========

def image_tab(request):
    """이미지 탭 페이지"""
    images = ImageData.objects.order_by('-uploaded_at')
    return render(request, 'multimodal/image_tab.html', {'images': images})


def image_upload(request):
    """이미지 업로드 처리"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '제목 없음')
            image_file = request.FILES.get('image_file')

            if image_file:
                # 이미지 데이터 저장
                image_data = ImageData.objects.create(
                    title=title,
                    image_file=image_file,
                    user=request.user if request.user.is_authenticated else None
                )

                # 로그 기록
                ProcessingLog.objects.create(
                    content_type='image',
                    object_id=image_data.id,
                    process_type='upload',
                    status='success',
                    message=f'이미지 "{title}" 업로드 완료'
                )

                messages.success(request, '이미지가 성공적으로 업로드되었습니다.')
                return redirect('multimodal:image_detail', image_id=image_data.id)
            else:
                messages.error(request, '이미지 파일을 선택해주세요.')
        except Exception as e:
            messages.error(request, f'업로드 중 오류가 발생했습니다: {str(e)}')

    return redirect('multimodal:image_tab')


@csrf_exempt
def image_segment(request):
    """이미지 세그먼트 정보 저장"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_id = data.get('image_id')
            label = data.get('label', '')
            coordinates = data.get('coordinates', [])

            image_data = get_object_or_404(ImageData, id=image_id)

            # 세그먼트 정보 저장
            segment = ImageSegment.objects.create(
                image_data=image_data,
                label=label,
                coordinates=coordinates
            )

            # 로그 기록
            ProcessingLog.objects.create(
                content_type='image',
                object_id=image_data.id,
                process_type='segment',
                status='success',
                message=f'세그먼트 "{label}" 추가 완료'
            )

            return JsonResponse({'success': True, 'segment_id': segment.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def image_detail(request, image_id):
    """이미지 상세 페이지 (세그먼트 그리기 기능 포함)"""
    image_data = get_object_or_404(ImageData, id=image_id)
    segments = image_data.segments.all()
    return render(request, 'multimodal/image_detail.html', {
        'image_data': image_data,
        'segments': segments
    })


# ========== 텍스트 처리 관련 뷰 ==========

def text_tab(request):
    """텍스트 탭 페이지"""
    texts = TextData.objects.order_by('-created_at')
    return render(request, 'multimodal/text_tab.html', {'texts': texts})


def text_process(request):
    """텍스트 처리 (직접 입력)"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '제목 없음')
            original_text = request.POST.get('text', '')

            if original_text.strip():
                # 텍스트 처리
                processed_data = process_text_with_kiwi(original_text)

                # 데이터베이스에 저장
                text_data = TextData.objects.create(
                    title=title,
                    original_text=original_text,
                    processed_text=processed_data['processed_text'],
                    morphemes=processed_data['morphemes'],
                    keywords=processed_data['keywords'],
                    user=request.user if request.user.is_authenticated else None
                )

                # 로그 기록
                ProcessingLog.objects.create(
                    content_type='text',
                    object_id=text_data.id,
                    process_type='morpheme_analysis',
                    status='success',
                    message=f'텍스트 "{title}" 형태소 분석 완료'
                )

                messages.success(request, '텍스트 분석이 완료되었습니다.')
                return render(request, 'multimodal/text_result.html', {'text_data': text_data})
            else:
                messages.error(request, '텍스트를 입력해주세요.')
        except Exception as e:
            messages.error(request, f'텍스트 처리 중 오류가 발생했습니다: {str(e)}')

    return redirect('multimodal:text_tab')


def text_upload(request):
    """텍스트 파일 업로드"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '제목 없음')
            text_file = request.FILES.get('text_file')

            if text_file:
                # 파일 내용 읽기
                file_content = text_file.read().decode('utf-8')

                # 텍스트 처리
                processed_data = process_text_with_kiwi(file_content)

                # 데이터베이스에 저장
                text_data = TextData.objects.create(
                    title=title,
                    original_text=file_content,
                    processed_text=processed_data['processed_text'],
                    morphemes=processed_data['morphemes'],
                    keywords=processed_data['keywords'],
                    user=request.user if request.user.is_authenticated else None
                )

                # 로그 기록
                ProcessingLog.objects.create(
                    content_type='text',
                    object_id=text_data.id,
                    process_type='file_upload_analysis',
                    status='success',
                    message=f'텍스트 파일 "{title}" 업로드 및 분석 완료'
                )

                messages.success(request, '텍스트 파일 분석이 완료되었습니다.')
                return render(request, 'multimodal/text_result.html', {'text_data': text_data})
            else:
                messages.error(request, '텍스트 파일을 선택해주세요.')
        except Exception as e:
            messages.error(request, f'파일 처리 중 오류가 발생했습니다: {str(e)}')

    return redirect('multimodal:text_tab')


# ========== 음성 처리 관련 뷰 ==========

def audio_tab(request):
    """음성 탭 페이지"""
    audios = AudioData.objects.order_by('-uploaded_at')
    return render(request, 'multimodal/audio_tab.html', {'audios': audios})


def audio_upload(request):
    """음성 파일 업로드"""
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '제목 없음')
            audio_file = request.FILES.get('audio_file')

            if audio_file:
                # 음성 데이터 저장
                audio_data = AudioData.objects.create(
                    title=title,
                    audio_file=audio_file,
                    processing_status='pending',
                    user=request.user if request.user.is_authenticated else None
                )

                try:
                    # 음성 처리 (Whisper)
                    audio_data.processing_status = 'processing'
                    audio_data.save()

                    processed_data = process_audio_with_whisper(audio_data.audio_file.path)

                    # 결과 저장
                    audio_data.transcribed_text = processed_data['transcribed_text']
                    audio_data.extracted_keywords = processed_data['keywords']
                    audio_data.processing_status = 'completed'
                    audio_data.processed_at = timezone.now()
                    audio_data.save()

                    # 로그 기록
                    ProcessingLog.objects.create(
                        content_type='audio',
                        object_id=audio_data.id,
                        process_type='whisper_transcription',
                        status='success',
                        message=f'음성 "{title}" 변환 완료'
                    )

                    messages.success(request, '음성 변환이 완료되었습니다.')
                    return redirect('multimodal:audio_detail', audio_id=audio_data.id)

                except Exception as e:
                    audio_data.processing_status = 'error'
                    audio_data.save()

                    # 오류 로그 기록
                    ProcessingLog.objects.create(
                        content_type='audio',
                        object_id=audio_data.id,
                        process_type='whisper_transcription',
                        status='error',
                        message=f'음성 변환 실패: {str(e)}'
                    )

                    messages.error(request, f'음성 처리 중 오류가 발생했습니다: {str(e)}')
            else:
                messages.error(request, '음성 파일을 선택해주세요.')
        except Exception as e:
            messages.error(request, f'업로드 중 오류가 발생했습니다: {str(e)}')

    return redirect('multimodal:audio_tab')


def audio_detail(request, audio_id):
    """음성 상세 페이지 (변환 결과 표시)"""
    audio_data = get_object_or_404(AudioData, id=audio_id)
    return render(request, 'multimodal/audio_detail.html', {'audio_data': audio_data})
