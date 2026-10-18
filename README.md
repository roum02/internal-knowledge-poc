# internal-knowledge-poc

사내 문서를 검색하고 근거와 함께 답변하는 RAG PoC입니다.

현재 단계는 **로컬 PostgreSQL + pgvector 실행 환경**입니다. 문서 적재, 검색 API, 답변 생성은 이후 구현합니다.

## 준비

- Docker Desktop 또는 OrbStack을 설치하고 실행합니다.
- `docker version`에서 Client와 Server가 모두 표시되고, `docker compose version`이 실행되는지 확인합니다.
- 처음 받는 경우 아래 명령으로 저장소를 가져옵니다.

```bash
git clone https://github.com/roum02/internal-knowledge-poc.git
cd internal-knowledge-poc
```

## 실행

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

## 로컬 접속 정보

`.env.example`의 기본값 기준입니다.

| 항목 | 값 |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `5432` |
| Database | `knowledge` |
| User | `knowledge` |
| Password | `.env`의 `POSTGRES_PASSWORD` |

로컬에서 실행할 `ingest.py`와 FastAPI는 이 주소로 연결합니다. 나중에 FastAPI도 같은 Compose의 컨테이너로 실행하면 DB 주소는 `db:5432`를 사용합니다.

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
- `init-db.sql`과 초기 계정 설정은 **빈 데이터 볼륨의 첫 실행 때만** 적용됩니다. 기존 DB의 비밀번호나 스키마는 `.env` 또는 SQL 파일 수정만으로 변경되지 않습니다.
- `docker compose down -v`는 DB 데이터 볼륨까지 삭제하므로 일반적인 종료에는 사용하지 않습니다.
- EC2로 옮길 때는 별도의 비밀번호와 접근 제어를 설정합니다. 현재 설정은 로컬 개발용입니다.

## 파일 역할

- `docker-compose.yml`: DB 이미지, 환경 변수, 포트, 볼륨, 상태 확인 설정
- `init-db.sql`: 초기 DB에 pgvector 확장 활성화
- `.env.example`: 로컬 설정 예시

이미지는 [pgvector 공식 배포 이미지](https://github.com/pgvector/pgvector#docker)를 사용하며, 초기화와 데이터 볼륨은 [Postgres 이미지의 동작](https://hub.docker.com/_/postgres)을 따릅니다.
