# Data Automation — PDF 파싱 & RAG 파이프라인

## 프로젝트 개요

PDF 문서를 업로드하면 페이지별 텍스트 추출 → 한국어 법령 구조 파싱(章/節/條) → Article 단위 청킹 → ChromaDB 벡터 업서트 → RAG 챗봇까지 한 번에 처리하는 파이프라인입니다.

```
PDF 업로드
  → 텍스트 추출 (PyMuPDF) + 페이지 PNG 미리보기
  → 정규식 파싱 (+ 선택적 LLM 보정) → Article 생성
  → 청킹 → ChromaDB 업서트 (임베딩 선택적)
  → 질문 생성 (LLM)
  → RAG 챗 (ChromaDB 검색 → LLM 답변)
```

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Backend | FastAPI (Python 3.11), SQLAlchemy 2.x, Pydantic v2 |
| Frontend | Next.js 14 (App Router), TypeScript |
| Vector DB | ChromaDB (self-hosted, HTTP) |
| LLM | OpenAI-compatible 외부 엔드포인트 (예: Qwen2.5-7B-Instruct) |
| 임베딩 | sentence-transformers BAAI/bge-m3 (선택적) |
| DB | SQLite (기본값) → PostgreSQL 전환 가능 |
| 컨테이너 | Docker / docker-compose |

---

## 디렉토리 구조

```
.
├── backend/                    # FastAPI 앱
│   ├── app/
│   │   ├── api/                # 라우터 (documents, articles, chat)
│   │   ├── core/               # 설정(config.py), DB 세션(deps.py)
│   │   ├── models/             # SQLAlchemy 모델 (db.py)
│   │   ├── schemas/            # Pydantic 요청/응답 스키마
│   │   ├── services/           # 핵심 로직 (pdf.py: 파싱·청킹·임베딩·RAG)
│   │   └── main.py             # FastAPI 앱 엔트리포인트, CORS, StaticFiles
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # Next.js 앱
│   ├── src/
│   │   ├── app/                # App Router
│   │   │   ├── page.tsx        # / — 문서 목록 + 업로드
│   │   │   ├── documents/[id]/ # /documents/:id — 상세 (미리보기, 파싱, 업서트)
│   │   │   └── chat/           # /chat — RAG 챗봇
│   │   ├── components/         # 공유 컴포넌트 (향후 추가)
│   │   └── lib/api.ts          # 백엔드 API 클라이언트 (중앙화)
│   ├── Dockerfile              # dev / builder / runner 3-stage
│   ├── package.json
│   └── .env.example
├── deploy/
│   └── k8s/                    # Kubernetes 매니페스트 (TODO 주석 포함)
│       ├── namespace.yaml
│       ├── configmap.yaml
│       ├── secret.yaml
│       ├── pvc-db.yaml
│       ├── pvc-media.yaml
│       ├── chroma.yaml
│       ├── django-deployment.yaml  # FastAPI backend Deployment
│       ├── django-service.yaml     # FastAPI backend Service (rag-backend)
│       └── ingress.yaml            # NGINX Ingress (Traefik annotation 제거)
├── docker-compose.yaml         # 로컬 개발 기준 (backend + frontend + chroma)
├── .env.example                # 루트 통합 환경변수 예시
└── README.md
```

---

## 로컬 실행 (docker-compose)

```bash
# 1. 환경변수 파일 생성
cp .env.example .env
# .env 를 열어 필요한 값 수정 (최소한 LLM_BASE_URL 확인)

# 2. 서비스 기동 (최초는 이미지 빌드 포함)
docker compose up --build

# 3. 접속
#   Frontend  : http://localhost:3000
#   Backend   : http://localhost:8000
#   API docs  : http://localhost:8000/docs
#   ChromaDB  : http://localhost:8001
```

> **hot reload**: backend(`uvicorn --reload`)와 frontend(`next dev`)는 소스 변경 시 자동 재시작됩니다.

### 개별 재시작 / 로그

```bash
docker compose restart backend
docker compose logs -f backend
```

---

## 환경변수

루트 `.env` 파일에 작성합니다. `docker compose`는 `.env`를 자동으로 읽습니다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SECRET_KEY` | `changeme-…` | FastAPI 서명 키 (프로덕션에서 반드시 변경) |
| `DEBUG` | `true` | 디버그 모드 |
| `DATABASE_URL` | `sqlite:///./data/db.sqlite3` | SQLAlchemy DB URL. PostgreSQL: `postgresql://user:pw@host/db` |
| `MEDIA_ROOT` | `./media` | 업로드 파일·미리보기 PNG 저장 경로 |
| `DOCUMENT_CHUNK_SIZE` | `1000` | 청킹 단위 (문자 수) |
| `DOCUMENT_CHUNK_OVERLAP` | `100` | 청크 간 중첩 (문자 수) |
| `EMBEDDING_PROVIDER` | `none` | `none` / `sentence_transformer` |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-m3` | sentence-transformers 모델명 |
| `VECTOR_DB_PROVIDER` | `chroma` | `chroma` / `none` |
| `CHROMA_URL` | `http://localhost:8001` | ChromaDB HTTP URL |
| `CHROMA_COLLECTION` | `documents` | 컬렉션명 |
| `LLM_PROVIDER` | `openai_compat` | `openai_compat` / `none` |
| `LLM_BASE_URL` | `http://localhost:11434` | LLM 엔드포인트 (Ollama 등) |
| `LLM_MODEL` | `Qwen2.5-7B-Instruct` | 모델명 |
| `LLM_API_KEY` | *(빈 값)* | Bearer 토큰 (필요 시) |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM 요청 타임아웃 |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | 브라우저에서 백엔드 호출 URL |
| `CORS_ORIGINS` | `http://localhost:3000` | 허용 CORS 오리진 (쉼표 구분) |

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/documents/upload/` | PDF 업로드 + 즉시 인제스트 |
| `GET` | `/api/documents/` | 문서 목록 (최근 50개) |
| `GET` | `/api/documents/{id}` | 문서 상세 (articles 포함) |
| `GET` | `/api/documents/{id}/pages/` | 페이지 목록 (미리보기 URL 포함) |
| `GET` | `/api/documents/{id}/pages/{page}/preview/` | 페이지 PNG 반환 |
| `POST` | `/api/documents/{id}/parse/` | 범위 파싱 → Article 생성 |
| `PUT` | `/api/articles/{id}/` | Article 수동 수정 |
| `POST` | `/api/documents/{id}/upsert/` | ChromaDB 업서트 |
| `POST` | `/api/documents/{id}/generate-questions/` | 질문 자동 생성 |
| `POST` | `/api/chat/` | RAG 챗 (`{ query, top_k }`) |

전체 스키마: **http://localhost:8000/docs** (Swagger UI 자동 생성)

---

## Kubernetes 배포 (deploy/k8s/)

각 파일의 `# TODO` 주석을 확인한 후 아래 순서로 적용하세요.

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/secret.yaml           # SECRET_KEY 먼저 수정
kubectl apply -f deploy/k8s/configmap.yaml        # 도메인, LLM_BASE_URL 수정
kubectl apply -f deploy/k8s/pvc-db.yaml
kubectl apply -f deploy/k8s/pvc-media.yaml
kubectl apply -f deploy/k8s/chroma.yaml
kubectl apply -f deploy/k8s/django-deployment.yaml  # 이미지 태그 수정 필요
kubectl apply -f deploy/k8s/django-service.yaml
kubectl apply -f deploy/k8s/ingress.yaml            # 도메인, TLS secret 수정 필요
```

> - `ingressClassName: nginx` — 클러스터 IngressClass 확인: `kubectl get ingressclass`
> - `storageClassName: local-path` — 클러스터 StorageClass에 맞게 수정
> - TLS secret `rag-tls`는 cert-manager 또는 수동으로 사전 생성 필요

---

## 스모크 테스트

```bash
BASE=http://localhost:8000

# 헬스 체크
curl $BASE/

# PDF 업로드 (DOC_ID는 응답의 id)
curl -F "file=@sample.pdf" $BASE/api/documents/upload/

# 페이지 목록 확인
curl $BASE/api/documents/DOC_ID/pages/

# 파싱 실행
curl -X POST $BASE/api/documents/DOC_ID/parse/ \
     -H "Content-Type: application/json" \
     -d '{"page_start":1,"page_end":10,"mode":"hybrid"}'

# ChromaDB 업서트 (EMBEDDING_PROVIDER=sentence_transformer 필요)
curl -X POST $BASE/api/documents/DOC_ID/upsert/

# RAG 챗 질의
curl -X POST $BASE/api/chat/ \
     -H "Content-Type: application/json" \
     -d '{"query":"제1조의 내용은 무엇인가요?","top_k":5}'
```

---

## 추후 작업 (TODO)

- [ ] PostgreSQL 전환 (`DATABASE_URL` 변경 + `psycopg2-binary` 추가만으로 가능)
- [ ] Alembic 마이그레이션 추가
- [ ] 임베딩 모델 활성화 (`EMBEDDING_PROVIDER=sentence_transformer`)
- [ ] K8s frontend Deployment/Service 추가
- [ ] CI/CD 파이프라인 (이미지 빌드 + 자동 배포)
