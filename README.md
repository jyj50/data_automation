# 멀티모달 데이터 전처리 & 분석 자동화 플랫폼

Django 기반의 웹 애플리케이션으로, 이미지, 텍스트, 음성 데이터를 전처리하고 분석할 수 있는 통합 플랫폼입니다. 데이터 분석가 포트폴리오용으로 제작된 라이트 버전입니다.

## 🚀 주요 기능

### 📸 이미지 처리
- 이미지 업로드 및 관리
- 마우스를 이용한 직접 세그먼트 그리기
- 객체 라벨링 (음식 종류 등)
- 세그먼트 정보 데이터베이스 저장

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
│   ├── utils.py           # 유틸리티 함수
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
├── staticfiles/           # 정적 파일 (배포용)
├── requirements.txt       # Python 패키지 의존성
├── manage.py             # Django 관리 스크립트
└── README.md
```

## 💡 사용 방법

### 이미지 처리
1. "이미지" 탭 클릭
2. 제목 입력 후 이미지 파일 업로드
3. 업로드된 이미지 클릭하여 상세 페이지 이동
4. 마우스로 객체 주위에 세그먼트 그리기
5. 객체 라벨 (음식 종류) 입력 후 저장

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
- 추가 AI 모델 연동 (YOLO, BERT 등)
- 데이터 시각화 라이브러리 연동
- RESTful API 구현
- 사용자 인증 시스템
- 배치 처리 시스템

### 라이브러리 설치 주의사항
```bash
# Kiwi 설치 (한국어 형태소 분석)
pip install kiwipiepy

# Whisper 설치 (음성 변환)
pip install openai-whisper torch torchaudio

# Windows에서 추가 설치 필요
pip install python-magic-bin
```

## 🎯 주요 특징

1. **직관적인 UI/UX**: 최소한의 디자인으로 기능에 집중
2. **실시간 처리**: 업로드와 동시에 자동 처리
3. **다국어 지원**: 한국어 최적화
4. **확장 가능한 구조**: 모듈화된 코드 구조
5. **데이터 영속성**: SQLite를 통한 결과 저장

## 📄 라이선스

이 프로젝트는 포트폴리오 목적으로 제작되었습니다.

## 👨‍💻 개발자 정보

데이터 분석가 포트폴리오용 프로젝트로 개발되었습니다.

---

**Note**: 이 프로젝트는 학습 및 포트폴리오 목적으로 제작된 라이트 버전입니다. 실제 운영 환경에서 사용하기 위해서는 추가적인 보안 설정과 최적화가 필요합니다.
