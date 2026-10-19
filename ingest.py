"""docs/의 Markdown을 나누고 임베딩한 뒤 PostgreSQL에 저장합니다."""

import argparse
import sys
from time import perf_counter

import psycopg

from database import connect, ensure_schema, replace_document
from embeddings import Embedder
from settings import ROOT


def chunk_text(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    """첫 PoC에서는 글자 수로 자르고 경계의 문맥을 위해 일부를 겹칩니다."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("chunk-size는 양수이고 overlap은 0 이상 chunk-size 미만이어야 합니다.")
    text = text.strip()
    chunks = []
    for start in range(0, len(text), size - overlap):
        chunk = text[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        if start + size >= len(text):
            break
    return chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-size", type=int, default=500, help="조각의 최대 글자 수 (기본 500)")
    parser.add_argument("--overlap", type=int, default=80, help="이웃 조각 사이 겹치는 글자 수 (기본 80)")
    args = parser.parse_args()
    started = perf_counter()
    try:
        chunk_text("", args.chunk_size, args.overlap)
        paths = sorted((ROOT / "docs").rglob("*.md"))
        if not paths:
            raise ValueError("docs/ 안에 적재할 .md 파일을 추가하세요.")
        documents = []
        for path in paths:
            source = path.relative_to(ROOT).as_posix()
            chunks = chunk_text(path.read_text(encoding="utf-8"), args.chunk_size, args.overlap)
            if not chunks:
                raise ValueError(f"빈 문서입니다: {source}. 내용을 채운 뒤 다시 실행하세요.")
            documents.append((source, chunks))

        with connect() as conn:
            ensure_schema(conn)
            embedder = Embedder()
            total = 0
            for source, chunks in documents:
                vectors = embedder.documents(chunks)
                replace_document(conn, source, chunks, vectors)
                total += len(chunks)
                print(f"저장: {source} → {len(chunks)}개 조각 (1024차원)", flush=True)
        print(f"완료: 문서 {len(documents)}개, 조각 {total}개, {perf_counter() - started:.1f}초")
    except (ValueError, OSError, RuntimeError, psycopg.Error) as exc:
        print(f"적재 실패: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
