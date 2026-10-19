"""문서와 질문을 같은 로컬 모델의 1024차원 벡터로 변환합니다."""

import os

import numpy as np

from settings import DIMENSIONS, MODEL_NAME, MODEL_REVISION, ROOT

# 모델 캐시는 프로젝트 안에 두며 Git에서 제외합니다.
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
# 작은 로컬 PoC에서는 별도 Xet 전송 계층 없이 일반 HTTPS로 내려받습니다.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


class Embedder:
    def __init__(self):
        # --help, 문서 검사, DB 연결에는 모델을 내려받거나 로드하지 않습니다.
        from sentence_transformers import SentenceTransformer

        device = os.getenv("EMBEDDING_DEVICE", "cpu")
        print(f"임베딩 모델 로드: {MODEL_NAME} ({device})", flush=True)
        self.model = SentenceTransformer(
            MODEL_NAME,
            revision=MODEL_REVISION,
            device=device,
            trust_remote_code=False,
        )
        self.model.max_seq_length = 2048

    def _encode(self, texts: list[str], *, query: bool) -> np.ndarray:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("임베딩할 텍스트가 비어 있습니다.")
        prompt = self.model.prompts["query"] if query else ""
        for text in texts:
            tokens = self.model.tokenizer(prompt + text, truncation=False)["input_ids"]
            if len(tokens) > self.model.max_seq_length:
                raise ValueError("입력이 2048토큰을 넘습니다. 문서 조각 또는 질문을 줄이세요.")

        # Qwen은 질문에 검색용 지시문을 붙이고 문서에는 붙이지 않습니다.
        options = {"prompt_name": "query"} if query else {"prompt": ""}
        vectors = self.model.encode(
            texts,
            batch_size=4,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            **options,
        ).astype(np.float32)
        if vectors.shape != (len(texts), DIMENSIONS) or not np.isfinite(vectors).all():
            raise ValueError("모델 출력의 차원 또는 값이 올바르지 않습니다.")
        return vectors

    def documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts, query=False)

    def query(self, text: str) -> np.ndarray:
        return self._encode([text], query=True)[0]
