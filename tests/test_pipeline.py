"""단위 검사 및 실제 pgvector를 사용하는 선택적 DB 회귀 검사.

TEST_DATABASE=1 python -m unittest discover -s tests -v
DB 검사는 세션 전용 임시 테이블을 사용합니다.
"""

import os
import unittest

import numpy as np
import psycopg

from database import connect, replace_document, search_chunks
from ingest import chunk_text
from settings import DIMENSIONS, MODEL_KEY, ROOT


class ChunkTests(unittest.TestCase):
    def test_overlap_preserves_all_text_and_final_tail(self):
        text = "가나다라마바사아자차카타파하" * 73
        chunks = chunk_text(text, size=500, overlap=80)
        rebuilt = chunks[0] + "".join(chunk[80:] for chunk in chunks[1:])
        self.assertEqual(rebuilt, text)
        self.assertTrue(all(0 < len(chunk) <= 500 for chunk in chunks))

    def test_exact_boundary_does_not_add_redundant_tail(self):
        self.assertEqual(chunk_text("가" * 500), ["가" * 500])
        self.assertEqual(chunk_text(" \n\t "), [])

    def test_invalid_overlap_cannot_loop_or_drop_text(self):
        for size, overlap in [(0, 0), (10, 10), (10, -1), (10, 11)]:
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                chunk_text("내용", size, overlap)


@unittest.skipUnless(os.getenv("TEST_DATABASE") == "1", "TEST_DATABASE=1일 때 DB 검사 실행")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = connect()
        ddl = (ROOT / "schema.sql").read_text(encoding="utf-8")
        cls.conn.execute(ddl.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.execute("TRUNCATE pg_temp.document_chunks")
        self.a = np.zeros(DIMENSIONS, dtype=np.float32)
        self.b = np.zeros(DIMENSIONS, dtype=np.float32)
        self.a[0] = 1
        self.b[1] = 1

    def test_reingestion_replaces_chunks_including_removed_tail(self):
        replace_document(self.conn, "docs/a.md", ["앞부분", "뒷부분"], [self.a, self.b])
        replace_document(self.conn, "docs/b.md", ["다른 문서"], [self.b])
        replace_document(self.conn, "docs/a.md", ["짧아진 문서"], [self.a])
        rows = self.conn.execute(
            "SELECT source, chunk_index, content FROM document_chunks ORDER BY source, chunk_index"
        ).fetchall()
        self.assertEqual(rows, [("docs/a.md", 0, "짧아진 문서"), ("docs/b.md", 0, "다른 문서")])

    def test_failed_insert_rolls_back_document_deletion(self):
        replace_document(self.conn, "docs/a.md", ["원래 내용"], [self.a])
        with self.assertRaises(psycopg.Error):
            replace_document(self.conn, "docs/a.md", ["새 내용"], [np.ones(3, dtype=np.float32)])
        self.assertEqual(
            self.conn.execute("SELECT content FROM document_chunks").fetchall(), [("원래 내용",)]
        )

    def test_cosine_search_ranks_and_filters_embedding_model(self):
        replace_document(self.conn, "docs/other.md", ["관련 낮은 문서"], [self.b])
        replace_document(self.conn, "docs/relevant.md", ["관련 문서"], [self.a])
        replace_document(self.conn, "docs/different-model.md", ["다른 모델"], [self.a])
        self.conn.execute(
            "UPDATE document_chunks SET embedding_model = %s WHERE source = %s",
            (MODEL_KEY + "-other", "docs/different-model.md"),
        )
        rows = search_chunks(self.conn, self.a, limit=3)
        self.assertEqual([row[0] for row in rows], ["docs/relevant.md", "docs/other.md"])
        self.assertAlmostEqual(rows[0][3], 1.0, places=5)
        self.assertAlmostEqual(rows[1][3], 0.0, places=5)


if __name__ == "__main__":
    unittest.main()
