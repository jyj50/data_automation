# PDF 문서 파싱 & RAG 준비 파이프라인 (Django 5.x)

## 주요 기능
- PDF 업로드 → 페이지별 텍스트 추출/정리 → 페이지 미리보기 PNG → 범위 파싱(장/절/조) → Article 단위 청킹 → 선택적으로 ChromaDB 업서트 → 질문 생성 → RAG 챗.
- 벡터 DB는 **ChromaDB(자가 호스팅)** 만 사용하며 HTTP로 연결합니다. LLM은 클러스터 외부(OpenAI 호환, 예: Qwen2.5 7B 서버)에서 호출합니다.
- 업로드 파일·썸네일·SQLite를 PVC에 두어 파드 재시작 후에도 유지됩니다.

## 로컬 실행
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
브라우저에서 http://127.0.0.1:8000/ 로 접속해 기존 UI/API 흐름을 그대로 사용하세요.

## 컨테이너
- 빌드: `docker build -t <registry>/data-automation:latest .`
- 푸시: `docker push <registry>/data-automation:latest`
- 로컬 실행(미디어/DB 유지):
  `docker run -p 8000:8000 -v $(pwd)/media:/app/media -v $(pwd)/data:/data --env-file <env> <registry>/data-automation:latest`

## Kubernetes 배포(deploy/k8s)
아래 순서로 적용:
1) `namespace.yaml`, `configmap.yaml`, `secret.yaml`
2) `pvc-db.yaml`, `pvc-media.yaml`
3) `chroma.yaml`
4) `django-deployment.yaml`, `django-service.yaml`
5) `ingress.yaml`

참고:
- Django는 `/app/media`(업로드/미리보기)와 `/data/db.sqlite3`(선택) 를 PVC에 마운트합니다.
- Chroma StatefulSet은 `/chroma/data` 에 PVC를 연결하며 `http://chroma.rag-app.svc.cluster.local:8000` 으로 접근합니다.
- Ingress 호스트 `rag.example.com` 은 예시입니다. 실제 도메인에 맞춰 `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` 를 설정하세요. Ingress가 없으면 NodePort로 대체 가능합니다.
- `storageClassName` 이 다르면 클러스터 기본값에 맞춰 수정하세요.

## 환경변수
| 변수 | 로컬 기본값 | K8s 예시 |
| --- | --- | --- |
| SECRET_KEY | 개발용 문자열 | `rag-secret`에서 주입 |
| DEBUG | true | false |
| ALLOWED_HOSTS | *(DEBUG 시) | `rag.example.com` |
| CSRF_TRUSTED_ORIGINS | 빈 값 | `https://rag.example.com` |
| MEDIA_ROOT | `./media` | `/app/media` (PVC) |
| STATIC_ROOT | `./staticfiles` | `/app/staticfiles` |
| SQLITE_PATH | `./db.sqlite3` | `/data/db.sqlite3` (PVC) |
| DOCUMENT_CHUNK_SIZE / DOCUMENT_CHUNK_OVERLAP | 1000 / 100 | 동일 |
| EMBEDDING_PROVIDER | `none` (벡터 생략) | 임베딩 모델 준비 시 변경 |
| EMBEDDING_MODEL_NAME | `BAAI/bge-m3` | 동일 |
| VECTOR_DB_PROVIDER | `chroma` | `chroma` |
| CHROMA_URL / CHROMA_COLLECTION | 빈 값(폴백 검색) | `http://chroma.rag-app.svc.cluster.local:8000` / `documents` |
| LLM_PROVIDER | `openai_compat` | `openai_compat` 또는 `none` |
| LLM_BASE_URL | `http://localhost:11434` | 외부 LLM 엔드포인트 |
| LLM_MODEL / LLM_TIMEOUT_SECONDS | `Qwen2.5-7B-Instruct` / `30` | 동일 |

## 스모크 테스트(배포 후)
1. PDF 업로드
2. 페이지 미리보기 확인
3. 파싱 실행 → Article 목록 생성 확인
4. Chroma 업서트 → 상태 완료, 오류 없음 확인
5. `/api/chat/` 질의 시 Chroma 기반 응답(LLM off이면 regex/DB 폴백 응답)
6. 파드 재시작 후에도 업로드/미리보기가 유지되는지 확인(PVC)

## API (변경 없음)
- `POST /api/documents/upload/` (multipart `file=@sample.pdf`)
- `GET /api/documents/<id>/pages/`
- `GET /api/documents/<id>/pages/<page>/preview/`
- `POST /api/documents/<id>/parse/` `{page_start, page_end, mode, force_reparse}`
- `PUT /api/articles/<id>/`
- `POST /api/documents/<id>/upsert/`
- `POST /api/documents/<id>/generate-questions/` `{per_article, scope, article_ids}`
- `GET /chat/`, `POST /api/chat/` `{query, top_k}`

## 테스트
```bash
python manage.py test documents
```
