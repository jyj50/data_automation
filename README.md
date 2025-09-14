# 멀티모달 데이터 전처리 & 분석 자동화 플랫폼

## 🚀 주요 기능

### 📸 이미지 처리 & YOLO 학습 데이터 생성

- 이미지 업로드 및 관리
- 마우스를 이용한 직접 세그먼트 그리기
- 객체 라벨링 (음식 종류 등)
- 세그먼트 정보 데이터베이스 저장
- **🆕 YOLOv8 세그멘테이션 포맷 자동 변환**
  - DB 저장 시 자동으로 YOLO 학습용 데이터셋 생성
  - 좌표 정규화 (0~1 범위) 및 클래스 ID 매핑
  - classes.txt 자동 관리
  - images/ 및 labels/ 디렉터리 구조 자동 생성

### 📝 텍스트 분석

- 텍스트 직접 입력 또는 파일 업로드
- Kiwi 라이브러리를 이용한 한국어 형태소 분석
- 불용어 제거 및 키워드 추출
- 분석 결과 시각화

### 🎵 음성 변환

- 음성 파일 업로드 (MP3, WAV, M4A, FLAC, OGG)
- OpenAI Whisper 모델을 이용한 음성-텍스트 변환
- 변환된 텍스트에서 키워드 자동 추출
- 실시간 처리 상태 표시

## 🛠️ 기술 스택

- **Backend**: Django 5.0+, Python 3.10+
- **Database**: SQLite (개발용)
- **Frontend**: HTML5, CSS3, JavaScript
- **AI/ML**:
  - Kiwi (한국어 형태소 분석)
  - OpenAI Whisper (음성-텍스트 변환)
  - **🆕 YOLOv8 데이터셋 포맷 지원**
    - Pillow (이미지 처리)
    - 자동 세그멘테이션 라벨 변환

## 📋 설치 및 실행

### 1. 프로젝트 클론

```bash
git clone <repository-url>
cd data_automation
```

### 2. 가상환경 설정

```bash
# uv 사용 (권장)
uv venv -p 3.10
uv sync

# 또는 pip 사용
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 데이터베이스 초기화

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. 관리자 계정 생성 (선택사항)

```bash
python manage.py createsuperuser
```

### 5. 개발 서버 실행

```bash
python manage.py runserver
```

웹브라우저에서 `http://localhost:8000`으로 접속하여 플랫폼을 이용할 수 있습니다.

## 📁 프로젝트 구조

```
data_automation/
├── config/                 # Django 프로젝트 설정
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── multimodal/            # 메인 앱
│   ├── models.py          # 데이터 모델
│   ├── views.py           # 뷰 함수
│   ├── urls.py            # URL 라우팅
│   ├── utils.py           # 유틸리티 함수 (🆕 YOLO 변환 포함)
│   ├── signals.py         # 🆕 Django 시그널 핸들러
│   ├── apps.py            # 앱 설정 (🆕 시그널 등록)
│   ├── admin.py           # 관리자 페이지 설정
│   ├── migrations/        # 데이터베이스 마이그레이션
│   └── templates/         # HTML 템플릿
│       └── multimodal/
│           ├── base.html
│           ├── home.html
│           ├── image_tab.html
│           ├── image_detail.html
│           ├── text_tab.html
│           ├── text_result.html
│           ├── audio_tab.html
│           └── audio_detail.html
├── media/                 # 업로드된 파일 저장
│   ├── images/           # 원본 이미지 파일
│   └── yolo_dataset/     # 🆕 YOLO 학습 데이터셋
│       ├── images/       # YOLO용 이미지 파일
│       ├── labels/       # YOLO용 라벨 파일 (.txt)
│       └── classes.txt   # 클래스 매핑 파일
├── staticfiles/           # 정적 파일 (배포용)
├── requirements.txt       # Python 패키지 의존성
├── manage.py             # Django 관리 스크립트
├── test_yolo_conversion.py # 🆕 YOLO 변환 테스트 스크립트
└── README.md
```

## 💡 사용 방법

### 이미지 처리 및 YOLO 데이터 생성

1. "이미지" 탭 클릭
2. 제목 입력 후 이미지 파일 업로드
3. 업로드된 이미지 클릭하여 상세 페이지 이동
4. 마우스로 객체 주위에 세그먼트 그리기
5. 객체 라벨 (음식 종류) 입력 후 저장
6. **🆕 자동으로 YOLO 학습 데이터 생성됨**
   - `media/yolo_dataset/images/`에 이미지 복사
   - `media/yolo_dataset/labels/`에 정규화된 좌표 저장
   - `classes.txt`에 라벨 자동 등록

### 텍스트 분석

1. "텍스트" 탭 클릭
2. 텍스트 직접 입력 또는 txt 파일 업로드
3. 분석 결과 확인 (형태소, 키워드, 처리된 텍스트)

### 음성 변환

1. "음성" 탭 클릭
2. 음성 파일 업로드
3. 자동 변환 처리 대기
4. 변환된 텍스트 및 키워드 확인

## 🔧 설정 정보

### 지원 파일 형식

- **이미지**: JPG, JPEG, PNG, GIF, BMP (최대 10MB)
- **텍스트**: TXT 파일 (UTF-8 인코딩)
- **음성**: MP3, WAV, M4A, FLAC, OGG (최대 50MB)

### 데이터베이스 모델

- `ImageData`: 이미지 정보
- `ImageSegment`: 세그먼트 좌표 및 라벨
- `TextData`: 텍스트 분석 결과
- `AudioData`: 음성 변환 결과
- `ProcessingLog`: 처리 로그

## 📝 개발 참고사항

### 확장 가능성

- **🆕 YOLO 모델 학습**: 생성된 데이터셋으로 직접 모델 학습
- 추가 AI 모델 연동 (BERT, SAM 등)
- 데이터 시각화 라이브러리 연동
- RESTful API 구현
- 사용자 인증 시스템
- 배치 처리 시스템
- **🆕 데이터 증강 기능**: 회전, 크기 변경, 밝기 조절 등

### 라이브러리 설치 주의사항

```bash
# Kiwi 설치 (한국어 형태소 분석)
pip install kiwipiepy

# Whisper 설치 (음성 변환)
pip install openai-whisper torch torchaudio

# 🆕 YOLO 데이터 변환용 (이미지 처리)
pip install Pillow

# Windows에서 추가 설치 필요
pip install python-magic-bin
```

### 🆕 YOLO 변환 기능 테스트

```bash
# YOLO 변환 기능 테스트 실행
python test_yolo_conversion.py
```

## 🎯 주요 특징

1. **직관적인 UI/UX**: 최소한의 디자인으로 기능에 집중
2. **실시간 처리**: 업로드와 동시에 자동 처리
3. **다국어 지원**: 한국어 최적화
4. **확장 가능한 구조**: 모듈화된 코드 구조
5. **데이터 영속성**: SQLite를 통한 결과 저장
6. **🆕 자동 YOLO 데이터셋 생성**: 세그먼트 저장 시 자동으로 학습 데이터 변환
7. **🆕 Django 시그널 기반**: post_save 시그널로 실시간 자동 변환

---
