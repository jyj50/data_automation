from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ImageSegment
from .utils import save_yolo_annotation


@receiver(post_save, sender=ImageSegment)
def convert_to_yolo_on_save(sender, instance, created, **kwargs):
    """
    ImageSegment가 저장될 때 자동으로 YOLO 형식으로 변환하여 저장합니다.
    """
    try:
        # 새로 생성되거나 업데이트된 세그먼트를 YOLO 형식으로 저장
        label_path = save_yolo_annotation(instance)

        if label_path:
            print(f"YOLO 라벨 파일 저장 완료: {label_path}")
        else:
            print(f"YOLO 라벨 파일 저장 실패: {instance}")

    except Exception as e:
        print(f"YOLO 변환 시그널 처리 중 오류: {e}")