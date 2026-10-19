"""PostgreSQL 연결, 문서별 교체 저장, 코사인 유사도 검색."""

import psycopg
from pgvector.psycopg import register_vector

from settings import MODEL_KEY, ROOT, database_options


def connect():
    conn = psycopg.connect(**database_options(), autocommit=True)
    try:
        register_vector(conn)
    except Exception:
        conn.close()
        raise
    return conn


def ensure_schema(conn):
    conn.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))


def replace_document(conn, source, chunks, vectors):
    if not chunks or len(chunks) != len(vectors):
        raise ValueError("문서 조각과 벡터의 개수가 일치해야 합니다.")
    # 임베딩이 끝난 뒤 한 트랜잭션으로 교체합니다. 저장 실패 시 원래 문서가 유지됩니다.
    with conn.transaction():
        conn.execute("DELETE FROM document_chunks WHERE source = %s", (source,))
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO document_chunks
                   (source, chunk_index, content, embedding, embedding_model)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (source, index, chunk, vector, MODEL_KEY)
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors))
                ],
            )


def search_chunks(conn, vector, limit=3):
    return conn.execute(
        """SELECT source, chunk_index, content,
                  1 - (embedding <=> %s) AS similarity
           FROM document_chunks
           WHERE embedding_model = %s
           ORDER BY embedding <=> %s, source, chunk_index
           LIMIT %s""",
        (vector, MODEL_KEY, vector, limit),
    ).fetchall()
