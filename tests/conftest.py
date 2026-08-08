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
from sqlalchemy.pool import StaticPool

from app.db import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def vector_store(tmp_path):
    from app.vector_store import VectorStore

    return VectorStore(path=str(tmp_path / "search.db"))


from fastapi.testclient import TestClient

from fixtures_data import JD_DATA, RESUME_DATA
from app.schemas import JDStructured


class FakeLLM:
    """可编程假 LLM：complete_structured 返回预设数据。"""

    def __init__(self, structured=None, text="ok"):
        self.structured = structured or {}
        self.text = text
        self.calls = []

    def complete(self, messages, max_tokens=2000):
        self.calls.append(("complete", messages))
        return self.text

    def complete_structured(self, messages, schema, max_tokens=2000):
        self.calls.append(("structured", messages))
        data = JD_DATA if schema is JDStructured else self.structured
        return schema.model_validate({**data}).model_dump()


@pytest.fixture
def client(db_session, vector_store, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "vector_store", vector_store)
    monkeypatch.setattr(main_module, "llm", FakeLLM(structured=RESUME_DATA))

    def override_get_session():
        yield db_session

    main_module.app.dependency_overrides[main_module.get_session] = override_get_session
    with TestClient(main_module.app) as c:
        yield c
    main_module.app.dependency_overrides.clear()
