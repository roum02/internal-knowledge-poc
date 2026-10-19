"""로컬 DB와 임베딩 설정. 모델과 차원은 적재·검색에서 동일하게 사용합니다."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
MODEL_KEY = f"{MODEL_NAME}@{MODEL_REVISION}"
DIMENSIONS = 1024


def database_options() -> dict:
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ValueError(".env에 POSTGRES_PASSWORD를 설정하세요. .env.example을 참고하세요.")
    return {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        # OrbStack 도메인처럼 컨테이너에 직접 접속할 때는 내부 포트를 지정합니다.
        "port": int(os.getenv("POSTGRES_CONNECT_PORT", os.getenv("POSTGRES_PORT", "5432"))),
        "dbname": os.getenv("POSTGRES_DB", "knowledge"),
        "user": os.getenv("POSTGRES_USER", "knowledge"),
        "password": password,
        "connect_timeout": 5,
    }
