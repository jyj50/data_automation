#!/usr/bin/env python
"""
YOLO 변환 기능 테스트 스크립트
Django 환경에서 YOLO 형식 변환을 테스트합니다.
"""

import os
import sys
import django
from pathlib import Path

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from multimodal.models import ImageData, ImageSegment
from multimodal.utils import convert_to_yolo_format, save_yolo_annotation, get_classes_mapping


def test_yolo_conversion():
    """YOLO 변환 기능을 테스트합니다."""
    print("=== YOLO 변환 기능 테스트 시작 ===")

    try:
        # 1. 기존 데이터 확인
        image_data_count = ImageData.objects.count()
        segment_count = ImageSegment.objects.count()

        print(f"기존 이미지 데이터: {image_data_count}개")
        print(f"기존 세그먼트 데이터: {segment_count}개")

        if segment_count == 0:
            print("테스트용 데이터가 없습니다. 샘플 데이터를 생성합니다.")
            create_sample_data()

        # 2. 세그먼트 데이터로 YOLO 변환 테스트
        segments = ImageSegment.objects.all()[:3]  # 처음 3개만 테스트

        for segment in segments:
            print(f"\n--- 세그먼트 테스트: {segment} ---")
            print(f"라벨: {segment.label}")
            print(f"좌표 개수: {len(segment.coordinates)}개")

            # YOLO 형식 변환 테스트
            yolo_line = convert_to_yolo_format(segment)
            if yolo_line:
                print(f"YOLO 형식: {yolo_line}")

                # 파일 저장 테스트
                label_path = save_yolo_annotation(segment)
                if label_path:
                    print(f"라벨 파일 저장: {label_path}")
                else:
                    print("라벨 파일 저장 실패")
            else:
                print("YOLO 형식 변환 실패")

        # 3. classes.txt 확인
        print(f"\n--- classes.txt 확인 ---")
        classes_mapping = get_classes_mapping()
        print(f"클래스 매핑: {classes_mapping}")

        # 4. 생성된 파일 확인
        from django.conf import settings
        yolo_dir = Path(settings.MEDIA_ROOT) / 'yolo_dataset'

        if yolo_dir.exists():
            labels_dir = yolo_dir / 'labels'
            images_dir = yolo_dir / 'images'
            classes_file = yolo_dir / 'classes.txt'

            print(f"\n--- 생성된 파일 확인 ---")
            print(f"YOLO 디렉터리: {yolo_dir}")

            if labels_dir.exists():
                label_files = list(labels_dir.glob("*.txt"))
                print(f"라벨 파일 수: {len(label_files)}개")
                for label_file in label_files[:3]:  # 처음 3개만 표시
                    print(f"  - {label_file.name}")

            if images_dir.exists():
                image_files = list(images_dir.glob("*"))
                print(f"이미지 파일 수: {len(image_files)}개")

            if classes_file.exists():
                with open(classes_file, 'r', encoding='utf-8') as f:
                    classes_content = f.read()
                print(f"classes.txt 내용:\n{classes_content}")

        print("\n=== YOLO 변환 기능 테스트 완료 ===")

    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def create_sample_data():
    """테스트용 샘플 데이터를 생성합니다."""
    print("샘플 데이터 생성을 위해 실제 이미지 파일과 세그먼트 데이터가 필요합니다.")
    print("Django admin이나 웹 인터페이스를 통해 이미지를 업로드하고 세그먼트를 생성한 후 다시 테스트해주세요.")


if __name__ == "__main__":
    test_yolo_conversion()