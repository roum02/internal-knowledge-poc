# internal-knowledge-poc

사내 문서를 검색하고 근거와 함께 답변하는 RAG PoC입니다.

현재 단계는 **로컬 PostgreSQL + pgvector에 문서를 적재하고, 질문과 관련된 문서 조각을 검색하는 CLI**입니다. 검색 API와 LLM 답변 생성은 다음 단계입니다.

```text
docs/*.md → ingest.py → 문서 조각 → 임베딩 → PostgreSQL에 저장
질문 → search.py → 질문 임베딩 → PostgreSQL에서 검색 → 출처와 원문 출력
```

## 준비

- Docker Desktop 또는 OrbStack을 설치하고 실행합니다.
- `docker version`에서 Client와 Server가 모두 표시되고, `docker compose version`이 실행되는지 확인합니다.
- 처음 받는 경우 아래 명령으로 저장소를 가져옵니다.

```bash
git clone https://github.com/roum02/internal-knowledge-poc.git
cd internal-knowledge-poc
```

## DB 실행

저장소 폴더에서 처음 한 번 환경 파일을 복사합니다. 이미 `.env`가 있으면 이 단계를 건너뜁니다.

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --wait db
docker compose ps
```

`.env.example`의 비밀번호는 로컬 개발용 예시입니다. `.env`는 Git에 올리지 않습니다. DB 포트는 `127.0.0.1`에만 바인딩하며, 데이터는 Docker의 `pgdata` 볼륨에 보관합니다.

첫 실행 시 `init-db.sql`이 `vector` 확장을 활성화합니다. 상태가 `healthy`인지 확인한 뒤 확장 버전과 벡터 연산을 확인합니다.

```bash
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT extversion FROM pg_extension WHERE extname = 'vector';
SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector AS distance;
SQL
```

예상 결과는 확장 버전 `0.8.7`, 거리 `1`입니다.

## 문서 적재와 검색

DB가 실행 중이면 저장소 폴더에서 Python 3.11 가상 환경을 만들고 패키지를 설치합니다. 기본 `python3`가 다른 버전일 수 있으므로 처음에는 `python3.11`을 명시합니다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# docs/의 Markdown 파일을 DB에 저장합니다.
python ingest.py

# 질문과 가까운 문서 조각 3개를 확인합니다.
python search.py "휴가 어떻게 신청해?" --top-k 3
```

새 터미널에서는 저장소 폴더로 이동한 뒤 `source .venv/bin/activate`로 가상 환경을 다시 활성화합니다. `python3.11`이 없다면 Python 3.11을 먼저 설치해야 합니다.

`docs/`에는 휴가, 비용 정산, VPN 이용에 관한 **가상의 예시 문서**가 있습니다. 실제 사내 규정이 아닙니다. 적재 후 아래 질문도 시도해 볼 수 있습니다.

```bash
python search.py "출장비는 어떻게 정산해?"
python search.py "집에서 사내 시스템에 접속하려면?"
```

첫 실행은 [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) 모델을 약 1.2 GB 내려받으므로 인터넷 연결과 시간이 필요합니다. 기본 캐시는 프로젝트의 `.cache/huggingface/`에 저장하며 `.cache/`는 Git에서 제외합니다. 이미 `HF_HOME`을 설정했다면 그 경로를 사용합니다. 모델 추론은 로컬에서 실행합니다.

기본 실행 장치는 CPU입니다. 지원되는 Apple Silicon Mac에서는 `.env`에 `EMBEDDING_DEVICE=mps`를 설정해 GPU 사용을 시도할 수 있습니다. 실행 문제가 있으면 `cpu`로 되돌립니다. 기존 `.env`에는 새 설정을 추가하지 않아도 기본값으로 실행됩니다.

### 저장과 검색 과정

1. `ingest.py`가 `schema.sql`을 적용해 `document_chunks` 테이블을 만듭니다. 이미 실행 중인 DB에도 적용하므로 볼륨을 지우거나 `docker compose down -v`를 실행할 필요가 없습니다.
2. 문서를 최대 500글자씩 자르고 이웃 조각의 80글자를 겹칩니다. 각 조각의 원문, 출처 경로, 조각 번호, 1024차원 벡터, 모델 식별자를 저장합니다.
3. 문서와 질문은 `settings.py`에 고정한 동일한 모델 ID·리비전을 사용합니다. 질문에는 모델의 검색용 지시문을 붙이고 문서에는 붙이지 않습니다.
4. `search.py`가 pgvector의 코사인 거리(`<=>`)가 가까운 순서로 조각을 가져옵니다. 작은 PoC이므로 전체 벡터를 비교하는 정확 검색을 사용하며, HNSW 같은 근사 검색 인덱스는 아직 없습니다.

출력에는 **출처, 조각 번호, 원문, 코사인 유사도**가 표시됩니다. 유사도는 `1 - 코사인 거리`이며 **정답 확률이 아닙니다**. 관련 없는 질문에도 가장 가까운 조각은 반환되므로 원문을 함께 확인합니다. 질문 임베딩 시간과 DB 검색 시간도 따로 표시하며 모델을 처음 로드하는 시간은 제외합니다.

문서를 수정한 뒤 `python ingest.py`를 다시 실행하면, 같은 출처의 기존 조각을 문서별 트랜잭션으로 교체해 중복 저장하지 않습니다. 한 문서의 저장에 실패하면 그 문서의 기존 데이터는 유지됩니다. 다만 **파일을 삭제하거나 이름을 바꿔도 이전 출처의 데이터는 자동 삭제하지 않습니다**.

## 로컬 접속 정보

`.env.example`의 기본값 기준입니다.

| 항목 | 값 |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `5432` |
| Database | `knowledge` |
| User | `knowledge` |
| Password | `.env`의 `POSTGRES_PASSWORD` |

로컬의 `ingest.py`와 `search.py`는 `.env`를 읽어 이 주소로 연결합니다. 나중에 FastAPI도 같은 Compose의 컨테이너로 실행하면 DB 주소는 `db:5432`를 사용합니다.

OrbStack에서 `localhost` 접속이 다른 PostgreSQL로 연결되는 경우에는 [Compose 서비스 도메인](https://docs.orbstack.dev/docker/domains#compose-projects)으로 DB를 직접 지정할 수 있습니다. 아래 설정을 `.env`에 넣으면 Python은 컨테이너 내부 포트 `5432`로 직접 연결하고, Compose의 Mac 공개 포트는 `5433`으로 분리합니다.

```dotenv
POSTGRES_HOST=db.internal-knowledge-poc.orb.local
POSTGRES_CONNECT_PORT=5432
POSTGRES_PORT=5433
```

`.env`를 변경한 뒤 `docker compose up -d --wait db`를 다시 실행해 공개 포트 변경을 적용합니다.

일반적인 `127.0.0.1` 연결에서는 `POSTGRES_CONNECT_PORT`를 생략하면 `POSTGRES_PORT`를 그대로 사용합니다. OrbStack 도메인은 OrbStack을 실행한 Mac에서만 사용할 수 있습니다.

## 코드 검사

```bash
# 문서 분할 검사
python -m unittest discover -s tests -v

# 실행 중인 DB의 pgvector로 재적재, 실패 시 복구, 검색 순위까지 검사
TEST_DATABASE=1 python -m unittest discover -s tests -v
```

DB 검사는 연결 세션에만 존재하는 임시 테이블을 사용합니다.

## 종료와 문제 확인

```bash
# 컨테이너를 종료합니다. DB 데이터는 유지됩니다.
docker compose down

# 다시 실행합니다.
docker compose up -d --wait db

# DB 로그를 확인합니다.
docker compose logs --tail=100 db
```

- `5432` 포트를 이미 사용 중이면 `.env`의 `POSTGRES_PORT`를 `5433` 등으로 바꾸고 다시 실행합니다. 로컬 앱의 접속 포트도 함께 바꿉니다.
- `init-db.sql`과 초기 계정 설정은 **빈 데이터 볼륨의 첫 실행 때만** 적용됩니다. 기존 DB 비밀번호는 `.env` 수정만으로 변경되지 않습니다. `schema.sql`은 `ingest.py`가 별도로 적용하지만, 기존 테이블 구조를 바꾸는 마이그레이션 기능은 없습니다.
- `docker compose down -v`는 DB 데이터 볼륨까지 삭제하므로 일반적인 종료에는 사용하지 않습니다.
- EC2로 옮길 때는 별도의 비밀번호와 접근 제어를 설정합니다. 현재 설정은 로컬 개발용입니다.

## 파일 역할

- `docker-compose.yml`: DB 이미지, 환경 변수, 포트, 볼륨, 상태 확인 설정
- `init-db.sql`: 초기 DB에 pgvector 확장 활성화
- `schema.sql`: 문서 조각과 1024차원 벡터를 저장할 테이블 정의
- `docs/`: 가상의 Markdown 예시 문서
- `ingest.py`: 문서 나누기, 임베딩 생성, DB 저장
- `search.py`: 질문으로 문서 조각 검색
- `embeddings.py`: 문서·질문 임베딩을 생성하는 공통 코드
- `database.py`: DB 연결, 문서별 교체 저장, 코사인 검색
- `settings.py`: DB 접속 설정과 모델 ID·리비전·차원
- `requirements.txt`: Python 패키지 목록
- `.env.example`: 로컬 설정 예시

이미지는 [pgvector 공식 배포 이미지](https://github.com/pgvector/pgvector#docker)를 사용하며, 초기화와 데이터 볼륨은 [Postgres 이미지의 동작](https://hub.docker.com/_/postgres)을 따릅니다.

임베딩은 [Qwen 공식 모델 사용법](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B#sentence-transformers-usage), Python과 DB 연결은 [pgvector-python의 Psycopg 3 사용법](https://github.com/pgvector/pgvector-python#psycopg-3)을 참고했습니다.
