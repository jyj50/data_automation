"""
멀티모달 데이터 처리를 위한 유틸리티 함수들
"""

import re
from collections import Counter


def process_text_with_kiwi(text):
    """
    Kiwi를 이용한 텍스트 처리 함수
    형태소 분석, 불용어 제거, 키워드 추출을 수행
    """
    try:
        # kiwipiepy가 설치되어 있다면 사용
        try:
            from kiwipiepy import Kiwi

            kiwi = Kiwi()

            # 형태소 분석
            tokens = kiwi.tokenize(text)
            morphemes = []
            processed_words = []

            # 불용어 리스트 (한국어 기준)
            stop_words = {
                "이",
                "그",
                "저",
                "것",
                "들",
                "에",
                "을",
                "를",
                "이",
                "가",
                "은",
                "는",
                "의",
                "로",
                "으로",
                "에서",
                "와",
                "과",
                "하고",
                "또",
                "그리고",
                "하지만",
                "그런데",
                "그러나",
                "또한",
                "이런",
                "그런",
                "저런",
                "같은",
                "다른",
                "많은",
                "적은",
                "좋은",
                "나쁜",
                "크다",
                "작다",
                "높다",
                "낮다",
                "있다",
                "없다",
                "되다",
                "하다",
                "말하다",
                "생각하다",
            }

            for token in tokens:
                word = token.form
                pos = token.tag

                # 형태소 정보 저장
                morphemes.append({"word": word, "pos": pos})

                # 명사, 동사, 형용사만 추출하고 불용어 제거
                if (
                    pos.startswith(("N", "V", "M"))
                    and len(word) > 1
                    and word not in stop_words
                ):
                    processed_words.append(word)

            # 처리된 텍스트 생성
            processed_text = " ".join(processed_words)

            # 키워드 추출 (빈도 기반)
            word_counter = Counter(processed_words)
            keywords = [word for word, count in word_counter.most_common(10)]

            return {
                "processed_text": processed_text,
                "morphemes": morphemes,
                "keywords": keywords,
            }

        except ImportError:
            # Kiwi가 없으면 간단한 정규식 기반 처리
            return process_text_simple(text)

    except Exception as e:
        print(f"텍스트 처리 중 오류 발생: {e}")
        return process_text_simple(text)


def process_text_simple(text):
    """
    Kiwi 없이 간단한 텍스트 처리
    정규식을 이용한 기본적인 전처리
    """
    # 특수문자 제거 및 정규화
    cleaned_text = re.sub(r"[^\w\s가-힣]", " ", text)
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    # 단어 분리
    words = cleaned_text.split()

    # 간단한 불용어 제거
    stop_words = {
        "이",
        "그",
        "저",
        "것",
        "들",
        "에",
        "을",
        "를",
        "이",
        "가",
        "은",
        "는",
        "의",
        "로",
        "으로",
        "에서",
        "와",
        "과",
        "하고",
        "그리고",
        "하지만",
        "있다",
        "없다",
        "되다",
        "하다",
    }

    # 불용어 제거 및 길이 필터링
    processed_words = [
        word for word in words if len(word) > 1 and word not in stop_words
    ]

    # 키워드 추출 (빈도 기반)
    word_counter = Counter(processed_words)
    keywords = [word for word, count in word_counter.most_common(10)]

    # 간단한 형태소 정보 생성
    morphemes = [{"word": word, "pos": "Unknown"} for word in words]

    return {
        "processed_text": " ".join(processed_words),
        "morphemes": morphemes,
        "keywords": keywords,
    }


def process_audio_with_whisper(audio_file_path):
    """
    OpenAI Whisper를 이용한 음성-텍스트 변환 및 키워드 추출
    """
    try:
        # Whisper가 설치되어 있다면 사용
        try:
            import whisper

            # Whisper 모델 로드 (base 모델 사용)
            model = whisper.load_model("base")

            # 음성 파일 변환
            result = model.transcribe(audio_file_path, language="ko")
            transcribed_text = result["text"]

            # 변환된 텍스트에서 키워드 추출
            text_analysis = process_text_with_kiwi(transcribed_text)

            return {
                "transcribed_text": transcribed_text,
                "keywords": text_analysis["keywords"],
            }

        except ImportError:
            # Whisper가 없으면 더미 데이터 반환
            return {
                "transcribed_text": "음성 변환 기능을 사용하려면 OpenAI Whisper를 설치해주세요.\n설치: pip install openai-whisper",
                "keywords": ["설치", "필요", "whisper", "openai"],
            }

    except Exception as e:
        return {
            "transcribed_text": f"음성 변환 중 오류가 발생했습니다: {str(e)}",
            "keywords": ["오류", "변환", "실패"],
        }


def extract_keywords_from_text(text, max_keywords=10):
    """
    텍스트에서 간단한 키워드 추출
    """
    # 텍스트 전처리
    processed_data = process_text_with_kiwi(text)
    return processed_data["keywords"][:max_keywords]


def validate_image_file(file):
    """
    이미지 파일 유효성 검사
    """
    allowed_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
    file_extension = file.name.lower().split(".")[-1]

    if f".{file_extension}" not in allowed_extensions:
        return (
            False,
            "지원되지 않는 이미지 형식입니다. (jpg, jpeg, png, gif, bmp만 지원)",
        )

    # 파일 크기 체크 (10MB 제한)
    if file.size > 10 * 1024 * 1024:
        return False, "파일 크기가 너무 큽니다. (10MB 이하만 허용)"

    return True, "유효한 이미지 파일입니다."


def validate_audio_file(file):
    """
    음성 파일 유효성 검사
    """
    allowed_extensions = [".mp3", ".wav", ".m4a", ".flac", ".ogg"]
    file_extension = file.name.lower().split(".")[-1]

    if f".{file_extension}" not in allowed_extensions:
        return False, "지원되지 않는 음성 형식입니다. (mp3, wav, m4a, flac, ogg만 지원)"

    # 파일 크기 체크 (50MB 제한)
    if file.size > 50 * 1024 * 1024:
        return False, "파일 크기가 너무 큽니다. (50MB 이하만 허용)"

    return True, "유효한 음성 파일입니다."


# YOLO 형식 변환 유틸리티 함수들


def get_classes_mapping():
    """classes.txt 파일에서 라벨 매핑을 읽어옵니다."""
    from django.conf import settings
    from pathlib import Path

    classes_file = Path(settings.MEDIA_ROOT) / "yolo_dataset" / "classes.txt"

    if not classes_file.exists():
        return {}

    mapping = {}
    with open(classes_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f.readlines()):
            label = line.strip()
            if label:
                mapping[label] = idx
    return mapping


def update_classes_mapping(new_label):
    """새로운 라벨을 classes.txt에 추가합니다."""
    from django.conf import settings
    from pathlib import Path

    yolo_dir = Path(settings.MEDIA_ROOT) / "yolo_dataset"
    yolo_dir.mkdir(exist_ok=True)

    classes_file = yolo_dir / "classes.txt"
    existing_classes = get_classes_mapping()

    if new_label not in existing_classes:
        with open(classes_file, "a", encoding="utf-8") as f:
            f.write(f"{new_label}\n")


def normalize_coordinates(coordinates, image_width, image_height):
    """좌표를 0~1 범위로 정규화합니다."""
    normalized = []
    for coord in coordinates:
        norm_x = coord["x"] / image_width
        norm_y = coord["y"] / image_height
        normalized.extend([norm_x, norm_y])
    return normalized


def convert_to_yolo_format(image_segment):
    """ImageSegment 인스턴스를 YOLO 형식으로 변환합니다."""
    try:
        from PIL import Image

        # 이미지 크기 정보 가져오기
        image_path = image_segment.image_data.image_file.path

        with Image.open(image_path) as img:
            image_width, image_height = img.size

        # 라벨을 클래스 ID로 변환
        classes_mapping = get_classes_mapping()
        update_classes_mapping(image_segment.label)

        # 매핑 다시 가져오기 (새 라벨이 추가되었을 수 있음)
        classes_mapping = get_classes_mapping()
        class_id = classes_mapping.get(image_segment.label, 0)

        # 좌표 정규화
        normalized_coords = normalize_coordinates(
            image_segment.coordinates, image_width, image_height
        )

        # YOLO 형식으로 포맷팅
        coord_str = " ".join([f"{coord:.6f}" for coord in normalized_coords])
        yolo_line = f"{class_id} {coord_str}"

        return yolo_line

    except Exception as e:
        print(f"YOLO 변환 오류: {e}")
        return None


def save_yolo_annotation(image_segment):
    """세그먼트를 YOLO 형식 라벨 파일로 저장합니다."""
    try:
        import shutil
        from django.conf import settings
        from pathlib import Path

        # YOLO 데이터셋 디렉터리 생성
        yolo_dir = Path(settings.MEDIA_ROOT) / "yolo_dataset"
        labels_dir = yolo_dir / "labels"
        images_dir = yolo_dir / "images"

        labels_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        # 이미지 파일명에서 라벨 파일명 생성
        image_filename = Path(image_segment.image_data.image_file.name).stem
        label_filename = f"{image_filename}.txt"
        label_path = labels_dir / label_filename

        # YOLO 형식으로 변환
        yolo_line = convert_to_yolo_format(image_segment)

        if yolo_line:
            # 기존 파일이 있다면 읽어서 해당 라벨 업데이트
            existing_lines = []
            if label_path.exists():
                with open(label_path, "r", encoding="utf-8") as f:
                    existing_lines = f.readlines()

            # 새 라인 추가
            existing_lines.append(f"{yolo_line}\n")

            # 파일에 저장
            with open(label_path, "w", encoding="utf-8") as f:
                f.writelines(existing_lines)

            # 이미지 복사 (YOLO 데이터셋 구조)
            source_image = Path(image_segment.image_data.image_file.path)
            target_image = images_dir / source_image.name

            if not target_image.exists():
                shutil.copy2(source_image, target_image)

            return label_path

    except Exception as e:
        print(f"YOLO 라벨 저장 오류: {e}")
        return None
