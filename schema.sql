-- 이미 실행 중인 DB에도 ingest.py가 이 파일을 적용합니다.
-- Qwen3-Embedding-0.6B의 기본 출력 차원은 1024입니다.
CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    content TEXT NOT NULL CHECK (length(btrim(content)) > 0),
    embedding VECTOR(1024) NOT NULL,
    embedding_model TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, chunk_index)
);

-- 소규모 PoC는 전체 벡터를 비교하는 정확 검색부터 시작합니다.
