import os
import sys
from pathlib import Path

# 必须在导入 app 之前设置，保证测试进程使用内存库且不写真实上传目录
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("UPLOAD_DIR", ".test_uploads")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


import chromadb


class DummyEmbeddingFunction(chromadb.EmbeddingFunction):
    """确定性哈希嵌入，测试用，避免下载真实嵌入模型。"""

    def __init__(self) -> None:
        pass

    def __call__(self, input):
        import hashlib

        vecs = []
        for doc in input:
            vec = [0.0] * 64
            for token in doc.split():
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                vec[int(digest, 16) % 64] += 1.0
            vecs.append(vec)
        return vecs

    @staticmethod
    def name() -> str:
        return "dummy_hash_embedding"

    def get_config(self) -> dict:
        return {}

    @classmethod
    def build_from_config(cls, config: dict) -> "DummyEmbeddingFunction":
        return cls()


@pytest.fixture
def vector_store():
    from app.vector_store import VectorStore

    return VectorStore(client=chromadb.EphemeralClient(), embedding_function=DummyEmbeddingFunction())
