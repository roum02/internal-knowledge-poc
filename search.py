"""질문과 가까운 문서 조각을 출처, 원문, 코사인 유사도와 함께 출력합니다."""

import argparse
import sys
from time import perf_counter

import psycopg

from database import connect, search_chunks
from embeddings import Embedder
from settings import MODEL_KEY


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="예: 휴가 어떻게 신청해?")
    parser.add_argument("--top-k", type=int, default=3, help="검색할 조각 수 (기본 3)")
    args = parser.parse_args()
    if not args.question.strip() or not 1 <= args.top_k <= 20:
        parser.error("질문은 비어 있을 수 없고 top-k는 1~20이어야 합니다.")
    try:
        with connect() as conn:
            if not conn.execute("SELECT to_regclass('document_chunks')").fetchone()[0]:
                raise ValueError("먼저 python ingest.py로 문서를 적재하세요.")
            count = conn.execute(
                "SELECT count(*) FROM document_chunks WHERE embedding_model = %s", (MODEL_KEY,)
            ).fetchone()[0]
            if count == 0:
                raise ValueError("현재 모델로 저장된 문서가 없습니다. python ingest.py를 실행하세요.")
            embedder = Embedder()
            started = perf_counter()
            vector = embedder.query(args.question)
            embedded = perf_counter()
            results = search_chunks(conn, vector, args.top_k)
            searched = perf_counter()
        for rank, (source, index, content, similarity) in enumerate(results, start=1):
            print(f"\n[{rank}] {source} · 조각 {index} · 유사도 {similarity:.4f}")
            print(content)
        print(
            f"\n질문 임베딩 {(embedded - started) * 1000:.0f}ms · "
            f"DB 검색 {(searched - embedded) * 1000:.1f}ms (모델 로드 제외)"
        )
        print("유사도는 정답 확률이 아닙니다. 관련 없는 질문도 가까운 순서대로 결과가 나옵니다.")
    except (ValueError, OSError, RuntimeError, psycopg.Error) as exc:
        print(f"검색 실패: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
