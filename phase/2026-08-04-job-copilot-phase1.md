# Job Copilot · Phase 1（核心闭环）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Job Copilot 核心闭环：上传简历 → 结构化确认 → 录入 JD → 匹配打分 → 生成自荐信，全程 SSE 进度推送，并带基础前端、Docker 与 CI。

**Architecture:** FastAPI 后端 + SQLAlchemy 2.0（SQLite）+ ChromaDB 向量库。简历与 JD 走「LLM 结构化输出 + 人工确认」；匹配用 LangGraph 三步工作流（规则关键词 → LLM 四维打分 → 差距归一化）；自荐信带 LLM-as-judge 自检重写循环；SSE 通过线程安全事件总线推送任务进度；React 前端消费 API 与 SSE。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / LangGraph / OpenAI SDK / ChromaDB / PyMuPDF / pytest / React 18 + Vite + Tailwind CSS / Docker。

**范围说明:** 本计划覆盖设计文档第 12 节的 Phase 1。Phase 2（JD 情报增强/投递管理）、Phase 3（面试陪练/评测平台）、Phase 4（打磨交付）在此计划完成后另立计划。Supervisor 路由在 Phase 2 引入，Phase 1 由服务层直接编排。

**项目根目录:** `job-copilot/`（在 Task 1 中创建）。所有相对路径均相对于该目录。

---

## 文件结构总览

```
job-copilot/
├── pyproject.toml              # 项目元数据与开发依赖
├── requirements.txt            # 运行时依赖（Docker 用）
├── .env.example                # 环境变量样例
├── .gitignore
├── README.md                   # 快速开始
├── Dockerfile
├── docker-compose.yml
├── .github/workflows/ci.yml    # CI：pytest + coverage
├── app/
│   ├── __init__.py
│   ├── config.py               # pydantic-settings 配置
│   ├── db.py                   # SQLAlchemy engine/session/Base
│   ├── models.py               # Resume / JD / Match 表
│   ├── schemas.py              # Pydantic 请求/结构化 schema
│   ├── llm.py                  # LLMService（补全 + 结构化输出 + 重试）
│   ├── vector_store.py         # ChromaDB 封装
│   ├── events.py               # 线程安全事件总线（SSE 用）
│   ├── main.py                 # FastAPI 入口 + 全部端点 + SSE
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── resume_agent.py     # 简历解析/结构化
│   │   └── jd_agent.py         # JD 结构化
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py             # ToolRouter
│   │   ├── pdf_parser.py       # PyMuPDF 文本提取
│   │   └── jd_fetcher.py       # URL 抓取 + 粗清理
│   ├── services/
│   │   ├── __init__.py
│   │   ├── resume_service.py   # 创建/确认简历 + 入库
│   │   ├── jd_service.py       # 文本/URL 创建 JD + 入库
│   │   ├── match_service.py    # 匹配编排 + 持久化
│   │   └── cover_letter_service.py  # 自荐信 + judge 循环
│   ├── workflow/
│   │   ├── __init__.py
│   │   └── graph.py            # LangGraph 匹配工作流
│   └── web/                    # React 前端（Milestone G）
│       ├── index.html
│       ├── package.json
│       ├── vite.config.js
│       ├── tailwind.config.js
│       ├── postcss.config.js
│       └── src/
│           ├── main.jsx
│           ├── App.jsx
│           ├── api.js
│           ├── index.css
│           └── components/
│               ├── ResumePanel.jsx
│               ├── JDPanel.jsx
│               └── MatchPanel.jsx
└── tests/
    ├── conftest.py             # db_session / vector_store / client fixture
    ├── fixtures_data.py        # RESUME_DATA / JD_DATA 样例
    ├── test_models.py
    ├── test_schemas.py
    ├── test_llm.py
    ├── test_vector_store.py
    ├── test_pdf_parser.py
    ├── test_jd_fetcher.py
    ├── test_resume_agent.py
    ├── test_resume_service.py
    ├── test_jd_service.py
    ├── test_match_workflow.py
    ├── test_match_service.py
    ├── test_cover_letter.py
    ├── test_events.py
    └── test_api.py
```

**模块边界（Phase 1）：**
- `app/llm.py`：唯一 LLM 出入口。其他模块只依赖 `complete` / `complete_structured`，不直接碰 SDK。
- `app/vector_store.py`：唯一向量库出入口。测试注入 EphemeralClient + 哑嵌入函数，不联网。
- `app/agents/*`：纯函数，做「文本 → 结构化」；不碰 DB、不碰 HTTP。
- `app/services/*`：编排 + DB 持久化 + 向量入库；接受 `llm` 与 `vector_store` 注入。
- `app/workflow/graph.py`：LangGraph 工作流，接受 `llm` 注入。
- `app/main.py`：HTTP 层，只做参数校验、任务调度、SSE；不写业务逻辑。

---

## Milestone A：项目骨架与数据基座

### Task 1: 创建项目目录与仓库

**Files:**
- Create: `job-copilot/`（项目根）
- Create: `job-copilot/.gitignore`
- Create: `job-copilot/pyproject.toml`
- Create: `job-copilot/requirements.txt`
- Create: `job-copilot/.env.example`

- [ ] **Step 1: 创建工作区并初始化 git**

```bash
mkdir job-copilot
cd job-copilot
git init -b main
```

Expected: `Initialized empty Git repository in .../job-copilot/.git/`

- [ ] **Step 2: 创建 `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.env
data/
node_modules/
app/web/dist/
.pytest_cache/
.coverage
.test_uploads/
```

- [ ] **Step 3: 创建 `pyproject.toml`**

```toml
[project]
name = "job-copilot"
version = "0.1.0"
description = "求职全生命周期 Agent"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",
    "sqlalchemy>=2.0.0",
    "langgraph>=0.2.0",
    "openai>=1.30.0",
    "chromadb>=0.5.0",
    "pymupdf>=1.24.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.9",
    "sse-starlette>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: 创建 `requirements.txt`（与 pyproject 依赖保持一致，Docker 使用）**

```txt
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.5.0
pydantic-settings>=2.0.0
sqlalchemy>=2.0.0
langgraph>=0.2.0
openai>=1.30.0
chromadb>=0.5.0
pymupdf>=1.24.0
httpx>=0.27.0
python-multipart>=0.0.9
sse-starlette>=2.0.0
python-dotenv>=1.0.0
```

- [ ] **Step 5: 创建 `.env.example`**

```bash
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
DATABASE_URL=sqlite:///./data/job_copilot.db
CHROMA_PATH=./data/chroma
UPLOAD_DIR=./data/uploads
```

- [ ] **Step 6: 提交**

```bash
git add .gitignore pyproject.toml requirements.txt .env.example
git commit -m "chore: 初始化项目骨架"
```

### Task 2: 配置、数据库基座与 ORM 模型

**Files:**
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/db.py`
- Create: `app/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败测试 `tests/test_models.py`**

```python
from app.models import JD, Match, Resume


def test_resume_crud(db_session):
    resume = Resume(
        source_type="file",
        raw_text="hello",
        structured_json={"name": "张三"},
        status="pending_confirmation",
    )
    db_session.add(resume)
    db_session.commit()
    loaded = db_session.get(Resume, resume.id)
    assert loaded.status == "pending_confirmation"
    assert loaded.structured_json["name"] == "张三"


def test_match_persists_scores_and_gaps(db_session):
    resume = Resume(raw_text="r", structured_json={})
    jd = JD(company="京东", title="LLM 应用开发实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(
        resume_id=resume.id,
        jd_id=jd.id,
        total_score=88.0,
        gaps_json=["缺少企业级项目经验"],
    )
    db_session.add(match)
    db_session.commit()
    loaded = db_session.get(Match, match.id)
    assert loaded.total_score == 88.0
    assert loaded.gaps_json == ["缺少企业级项目经验"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL（`ModuleNotFoundError: app`）

- [ ] **Step 3: 创建 `app/__init__.py`（空文件）**

- [ ] **Step 4: 创建 `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "job-copilot"
    database_url: str = "sqlite:///./data/job_copilot.db"
    chroma_path: str = "./data/chroma"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    upload_dir: str = "./data/uploads"
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
```

- [ ] **Step 5: 创建 `app/db.py`**

```python
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


if settings.database_url.startswith("sqlite"):
    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: 创建 `app/models.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(20), default="file")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending_confirmation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JD(Base):
    __tablename__ = "jds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(20), default="text")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id"))
    jd_id: Mapped[str] = mapped_column(ForeignKey("jds.id"))
    dimension_scores_json: Mapped[dict] = mapped_column(JSON, default=dict)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    gaps_json: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 7: 创建 `tests/conftest.py`（本任务先提供 db_session fixture；后续任务逐步追加）**

```python
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
```

- [ ] **Step 8: 运行测试确认通过**

Run: `pytest tests/test_models.py -v`
Expected: 2 passed

- [ ] **Step 9: 提交**

```bash
git add app tests
git commit -m "feat: 配置、数据库基座与 ORM 模型"
```

### Task 3: Pydantic Schemas

**Files:**
- Create: `app/schemas.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: 写失败测试 `tests/test_schemas.py`**

```python
from app.schemas import JDStructured, ResumeStructured


def test_resume_schema_accepts_sample():
    data = {
        "name": "张三",
        "email": "a@b.com",
        "phone": "13800000000",
        "city": "北京",
        "education": [
            {"school": "XX 大学", "degree": "硕士", "major": "计算机", "years": "2024-2027"}
        ],
        "experience": [],
        "projects": [],
        "skills": ["Python", "LangGraph"],
    }
    resume = ResumeStructured.model_validate(data)
    assert resume.skills == ["Python", "LangGraph"]
    assert resume.education[0].major == "计算机"


def test_jd_schema_defaults():
    jd = JDStructured.model_validate({})
    assert jd.requirements == []
    assert jd.company == ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL（`ModuleNotFoundError: app.schemas`）

- [ ] **Step 3: 创建 `app/schemas.py`**

```python
from pydantic import BaseModel


class Education(BaseModel):
    school: str = ""
    degree: str = ""
    major: str = ""
    years: str = ""


class Experience(BaseModel):
    company: str = ""
    role: str = ""
    years: str = ""
    highlights: list[str] = []


class Project(BaseModel):
    name: str = ""
    description: str = ""
    tech: list[str] = []
    highlights: list[str] = []


class ResumeStructured(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    education: list[Education] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    skills: list[str] = []


class JDStructured(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    salary: str = ""
    responsibilities: list[str] = []
    requirements: list[str] = []


class MatchRequest(BaseModel):
    resume_id: str
    jd_ids: list[str]


class DimensionScores(BaseModel):
    skill_match: float = 0.0
    experience_match: float = 0.0
    education_match: float = 0.0
    hard_requirements: float = 0.0


class MatchResult(BaseModel):
    match_id: str = ""
    jd_id: str = ""
    dimension_scores: DimensionScores = DimensionScores()
    reasons: dict[str, str] = {}
    total_score: float = 0.0
    gaps: list[str] = []
    summary: str = ""


class CoverLetterRequest(BaseModel):
    match_id: str
    tone: str = "standard"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_schemas.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add app/schemas.py tests/test_schemas.py
git commit -m "feat: Pydantic 结构化 schema"
```

---

## Milestone B：LLM、向量库与工具层

### Task 4: LLMService（补全 + 结构化输出 + 重试降级）

**Files:**
- Create: `app/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: 写失败测试 `tests/test_llm.py`**

```python
import json

from app.llm import LLMService
from app.schemas import ResumeStructured


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _FakeCompletions:
    def __init__(self, contents):
        self._contents = contents
        self.calls = 0

    def create(self, **kwargs):
        content = self._contents[min(self.calls, len(self._contents) - 1)]
        self.calls += 1
        return _Response(content)


class _FakeChat:
    def __init__(self, contents):
        self.completions = _FakeCompletions(contents)


class FakeClient:
    def __init__(self, contents):
        self.chat = _FakeChat(contents)


def test_complete_returns_text():
    client = FakeClient(["hello"])
    svc = LLMService(client=client)
    assert svc.complete([{"role": "user", "content": "hi"}]) == "hello"


def test_complete_structured_parses_fenced_json():
    payload = json.dumps({"name": "张三", "skills": ["Python"]}, ensure_ascii=False)
    client = FakeClient([f"```json\n{payload}\n```"])
    svc = LLMService(client=client)
    result = svc.complete_structured([{"role": "user", "content": "x"}], ResumeStructured)
    assert result["name"] == "张三"
    assert result["skills"] == ["Python"]


def test_complete_structured_retries_on_invalid_json():
    payload = json.dumps({"name": "李四"}, ensure_ascii=False)
    client = FakeClient(["not json", payload])
    svc = LLMService(client=client)
    result = svc.complete_structured([{"role": "user", "content": "x"}], ResumeStructured)
    assert result["name"] == "李四"
    assert client.chat.completions.calls == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL（`ModuleNotFoundError: app.llm`）

- [ ] **Step 3: 创建 `app/llm.py`**

```python
import json
import re
from typing import Any, Type

from openai import OpenAI
from pydantic import BaseModel

from app.config import settings


class LLMService:
    """LLM 调用封装：普通补全 + 结构化 JSON 输出，带一次重试。"""

    def __init__(self, client: OpenAI | None = None, model: str | None = None):
        self.client = client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "EMPTY",
        )
        self.model = model or settings.llm_model

    def complete(self, messages: list[dict[str, str]], max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[BaseModel],
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """要求模型输出符合 schema 的 JSON；解析失败时带错误信息重试一次。"""
        instruction = (
            "You must respond with a single JSON object matching this schema exactly:\n"
            f"{schema.model_json_schema()}\n"
            "No markdown fences. No commentary."
        )
        attempt_messages = messages + [{"role": "system", "content": instruction}]
        for attempt in range(2):
            text = self.complete(attempt_messages, max_tokens=max_tokens)
            try:
                data = self._extract_json(text)
                return schema.model_validate(data).model_dump()
            except Exception as exc:
                if attempt == 0:
                    attempt_messages = attempt_messages + [
                        {"role": "assistant", "content": text},
                        {
                            "role": "user",
                            "content": f"Previous output was invalid: {exc}. Return valid JSON.",
                        },
                    ]
                    continue
                raise ValueError(f"LLM structured output failed: {exc}") from exc
        raise ValueError("LLM structured output failed")

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_llm.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add app/llm.py tests/test_llm.py
git commit -m "feat: LLMService 与结构化输出重试"
```

### Task 5: VectorStore（ChromaDB 封装）

**Files:**
- Create: `app/vector_store.py`
- Test: `tests/test_vector_store.py`

- [ ] **Step 1: 在 `tests/conftest.py` 追加共享 fixture（哑嵌入函数 + vector_store）**

把下面内容追加到 `tests/conftest.py` 末尾：

```python
import chromadb


class DummyEmbeddingFunction:
    """确定性哈希嵌入，测试用，避免下载真实嵌入模型。"""

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


@pytest.fixture
def vector_store():
    from app.vector_store import VectorStore

    return VectorStore(client=chromadb.EphemeralClient(), embedding_function=DummyEmbeddingFunction())
```

- [ ] **Step 2: 写失败测试 `tests/test_vector_store.py`**

```python
from app.vector_store import COLLECTION_RESUMES


def test_add_and_query(vector_store):
    vector_store.add(
        COLLECTION_RESUMES,
        ["我会 Python 和 LangGraph", "我会 Java 和 Spring"],
        ["r1", "r2"],
        [{"resume_id": "r1"}, {"resume_id": "r2"}],
    )
    results = vector_store.query(COLLECTION_RESUMES, ["Python LangGraph"], top_k=1)
    assert results[0]["id"] == "r1"
    assert results[0]["metadata"]["resume_id"] == "r1"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_vector_store.py -v`
Expected: FAIL（`ModuleNotFoundError: app.vector_store`）

- [ ] **Step 4: 创建 `app/vector_store.py`**

```python
from typing import Any

import chromadb

from app.config import settings

COLLECTION_RESUMES = "resumes"
COLLECTION_JDS = "jds"


class VectorStore:
    """ChromaDB 封装：文档写入与向量检索。"""

    def __init__(
        self,
        path: str | None = None,
        client: Any | None = None,
        embedding_function: Any | None = None,
    ):
        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(path=path or settings.chroma_path)
        self._embedding_function = embedding_function
        self._collections: dict[str, Any] = {}

    def _collection(self, name: str):
        if name not in self._collections:
            kwargs = {}
            if self._embedding_function is not None:
                kwargs["embedding_function"] = self._embedding_function
            self._collections[name] = self._client.get_or_create_collection(name, **kwargs)
        return self._collections[name]

    def add(
        self,
        collection: str,
        docs: list[str],
        ids: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        self._collection(collection).upsert(
            documents=docs,
            ids=ids,
            metadatas=metadatas or [{}] * len(docs),
        )

    def query(self, collection: str, query_texts: list[str], top_k: int = 5) -> list[dict]:
        result = self._collection(collection).query(query_texts=query_texts, n_results=top_k)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0] or [{}] * len(docs)
        ids = result.get("ids", [[]])[0]
        return [
            {"id": ids[i], "text": docs[i], "metadata": metas[i]}
            for i in range(len(docs))
        ]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_vector_store.py -v`
Expected: 1 passed

- [ ] **Step 6: 提交**

```bash
git add app/vector_store.py tests/test_vector_store.py tests/conftest.py
git commit -m "feat: ChromaDB 向量库封装"
```

### Task 6: 工具层（PDF 解析 + URL 抓取 + ToolRouter）

**Files:**
- Create: `app/tools/__init__.py`
- Create: `app/tools/base.py`
- Create: `app/tools/pdf_parser.py`
- Create: `app/tools/jd_fetcher.py`
- Test: `tests/test_pdf_parser.py`
- Test: `tests/test_jd_fetcher.py`

- [ ] **Step 1: 写失败测试 `tests/test_pdf_parser.py`**

```python
import fitz

from app.tools.pdf_parser import extract_pdf_text


def test_extract_pdf_text(tmp_path):
    pdf_path = tmp_path / "resume.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "姓名：张三\n技能：Python")
    doc.save(str(pdf_path))
    doc.close()

    text = extract_pdf_text(str(pdf_path))
    assert "张三" in text
    assert "Python" in text
```

- [ ] **Step 2: 写失败测试 `tests/test_jd_fetcher.py`**

```python
from app.tools.jd_fetcher import fetch_url_text


def test_fetch_url_text_strips_script(monkeypatch):
    class FakeResponse:
        text = "<html><script>bad()</script><body>招聘 AI 产品实习生</body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("httpx.get", lambda *a, **k: FakeResponse())
    text = fetch_url_text("https://example.com/jd")
    assert "招聘 AI 产品实习生" in text
    assert "bad()" not in text
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_pdf_parser.py tests/test_jd_fetcher.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 4: 创建 `app/tools/__init__.py`（空文件）与 `app/tools/base.py`**

```python
from typing import Any, Callable

ToolFn = Callable[..., Any]


class ToolRouter:
    """工具注册与路由。Phase 2 起由 Supervisor 按需调用。"""

    def __init__(self):
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    def execute(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"tool not found: {name}")
        return self._tools[name](**kwargs)
```

- [ ] **Step 5: 创建 `app/tools/pdf_parser.py`**

```python
import fitz


def extract_pdf_text(path: str) -> str:
    """从 PDF 提取全文；空页返回空字符串。"""
    doc = fitz.open(path)
    try:
        parts = [page.get_text() for page in doc]
    finally:
        doc.close()
    return "\n".join(parts).strip()
```

- [ ] **Step 6: 创建 `app/tools/jd_fetcher.py`**

```python
import re

import httpx


def fetch_url_text(url: str, timeout: float = 15.0) -> str:
    """抓取公开网页文本并做粗粒度清理（去 script/style/标签）。"""
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    text = response.text
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
```

- [ ] **Step 7: 运行测试确认通过**

Run: `pytest tests/test_pdf_parser.py tests/test_jd_fetcher.py -v`
Expected: 2 passed

- [ ] **Step 8: 提交**

```bash
git add app/tools tests/test_pdf_parser.py tests/test_jd_fetcher.py
git commit -m "feat: PDF 解析、URL 抓取与工具路由"
```

---

## Milestone C：简历与 JD

### Task 7: 简历智能体（文本/PDF 结构化）

**Files:**
- Create: `tests/fixtures_data.py`
- Create: `app/agents/__init__.py`
- Create: `app/agents/resume_agent.py`
- Test: `tests/test_resume_agent.py`

- [ ] **Step 1: 创建 `tests/fixtures_data.py`（测试共用样例）**

```python
RESUME_DATA = {
    "name": "张三",
    "email": "zhangsan@example.com",
    "phone": "13800000000",
    "city": "北京",
    "education": [
        {"school": "XX 大学", "degree": "硕士", "major": "计算机科学与技术", "years": "2024-2027"}
    ],
    "experience": [
        {
            "company": "某科技公司",
            "role": "后端开发实习生",
            "years": "2025-06 至 2025-09",
            "highlights": ["实现 RAG 检索服务，QPS 提升 40%"],
        }
    ],
    "projects": [
        {
            "name": "DeepResearch-Agent",
            "description": "多 Agent 研究系统",
            "tech": ["LangGraph", "FastAPI", "ChromaDB"],
            "highlights": ["Planner-Researcher-Writer-Reviewer 四 Agent 协作"],
        }
    ],
    "skills": ["Python", "LangGraph", "FastAPI", "RAG", "SQL"],
}

JD_DATA = {
    "company": "京东",
    "title": "LLM 应用开发实习生",
    "location": "北京",
    "salary": "面议",
    "responsibilities": ["参与 Agent 功能开发", "维护 RAG 检索链路"],
    "requirements": ["熟悉 Python", "了解 LangGraph 或类似编排框架", "有 RAG 项目经验优先"],
}
```

- [ ] **Step 2: 写失败测试 `tests/test_resume_agent.py`**

```python
import fitz

from app.agents.resume_agent import parse_resume_pdf, parse_resume_text
from fixtures_data import RESUME_DATA


class FakeLLM:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def test_parse_resume_text():
    result = parse_resume_text("我叫张三，会 Python 和 LangGraph", FakeLLM(RESUME_DATA))
    assert result["name"] == "张三"
    assert result["skills"] == ["Python", "LangGraph", "FastAPI", "RAG", "SQL"]


def test_parse_resume_pdf(tmp_path):
    pdf_path = tmp_path / "r.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "姓名：张三")
    doc.save(str(pdf_path))
    doc.close()

    raw, structured = parse_resume_pdf(str(pdf_path), FakeLLM(RESUME_DATA))
    assert "张三" in raw
    assert structured["name"] == "张三"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_resume_agent.py -v`
Expected: FAIL（`ModuleNotFoundError: app.agents.resume_agent`）

- [ ] **Step 4: 创建 `app/agents/__init__.py`（空文件）与 `app/agents/resume_agent.py`**

```python
from app.llm import LLMService
from app.schemas import ResumeStructured
from app.tools.pdf_parser import extract_pdf_text


def parse_resume_text(raw_text: str, llm: LLMService | None = None) -> dict:
    """将简历文本结构化为 ResumeStructured。"""
    llm = llm or LLMService()
    messages = [
        {
            "role": "system",
            "content": "你是资深 HR 简历分析师。请把简历内容提取为结构化 JSON，缺失字段留空。",
        },
        {"role": "user", "content": raw_text[:20000]},
    ]
    return llm.complete_structured(messages, ResumeStructured)


def parse_resume_pdf(path: str, llm: LLMService | None = None) -> tuple[str, dict]:
    """解析 PDF 文件，返回 (原始文本, 结构化结果)。"""
    raw_text = extract_pdf_text(path)
    structured = parse_resume_text(raw_text, llm)
    return raw_text, structured
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_resume_agent.py -v`
Expected: 2 passed

- [ ] **Step 6: 提交**

```bash
git add app/agents tests/fixtures_data.py tests/test_resume_agent.py
git commit -m "feat: 简历智能体文本/PDF 结构化"
```

### Task 8: 简历服务（创建 + 人工确认 + 向量入库）

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/resume_service.py`
- Test: `tests/test_resume_service.py`

- [ ] **Step 1: 写失败测试 `tests/test_resume_service.py`**

```python
import fitz

from app.models import Resume
from app.services.resume_service import confirm_resume, create_resume_from_file
from fixtures_data import RESUME_DATA


class FakeLLM:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def _make_pdf(tmp_path):
    path = tmp_path / "r.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "姓名：张三 技能：Python LangGraph")
    doc.save(str(path))
    doc.close()
    return str(path)


def test_create_then_confirm_resume(db_session, vector_store, tmp_path):
    resume = create_resume_from_file(
        db_session, _make_pdf(tmp_path), vector_store, llm=FakeLLM(RESUME_DATA)
    )
    assert resume.status == "pending_confirmation"
    assert resume.structured_json["name"] == "张三"

    confirmed = confirm_resume(db_session, resume.id, resume.structured_json, vector_store)
    assert confirmed.status == "confirmed"

    hits = vector_store.query("resumes", ["Python LangGraph"], top_k=1)
    assert hits[0]["id"] == resume.id
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_resume_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.resume_service`）

- [ ] **Step 3: 创建 `app/services/__init__.py`（空文件）与 `app/services/resume_service.py`**

```python
import json

from sqlalchemy.orm import Session

from app.agents.resume_agent import parse_resume_pdf
from app.llm import LLMService
from app.models import Resume
from app.vector_store import COLLECTION_RESUMES, VectorStore


def create_resume_from_file(
    db: Session,
    file_path: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> Resume:
    raw_text, structured = parse_resume_pdf(file_path, llm)
    resume = Resume(
        source_type="file",
        file_path=file_path,
        raw_text=raw_text,
        structured_json=structured,
        status="pending_confirmation",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def confirm_resume(
    db: Session,
    resume_id: str,
    structured_json: dict,
    vector_store: VectorStore,
) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise KeyError(f"resume not found: {resume_id}")
    resume.structured_json = structured_json
    resume.status = "confirmed"
    db.commit()
    db.refresh(resume)
    vector_store.add(
        COLLECTION_RESUMES,
        [json.dumps(structured_json, ensure_ascii=False)],
        [resume.id],
        [{"resume_id": resume.id}],
    )
    return resume
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_resume_service.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add app/services tests/test_resume_service.py
git commit -m "feat: 简历服务（创建/确认/入库）"
```

### Task 9: JD 智能体与服务（文本/URL 创建 + 入库）

**Files:**
- Create: `app/agents/jd_agent.py`
- Create: `app/services/jd_service.py`
- Test: `tests/test_jd_service.py`

- [ ] **Step 1: 写失败测试 `tests/test_jd_service.py`**

```python
from app.services.jd_service import create_jd_from_text, create_jd_from_url
from fixtures_data import JD_DATA


class FakeLLM:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def test_create_jd_from_text(db_session, vector_store):
    jd = create_jd_from_text(
        db_session, "京东招聘 LLM 应用开发实习生", vector_store, llm=FakeLLM(JD_DATA)
    )
    assert jd.company == "京东"
    assert jd.title == "LLM 应用开发实习生"
    hits = vector_store.query("jds", ["LLM"], top_k=1)
    assert hits[0]["id"] == jd.id


def test_create_jd_from_url(db_session, vector_store, monkeypatch):
    class FakeResponse:
        text = "<html><body>岗位名称：AI 产品实习生</body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("httpx.get", lambda *a, **k: FakeResponse())
    jd = create_jd_from_url(
        db_session, "https://example.com/jd", vector_store, llm=FakeLLM(JD_DATA)
    )
    assert jd.source_type == "url"
    assert jd.source_url == "https://example.com/jd"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_jd_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.agents.jd_agent`）

- [ ] **Step 3: 创建 `app/agents/jd_agent.py`**

```python
from app.llm import LLMService
from app.schemas import JDStructured


def structure_jd_text(text: str, llm: LLMService | None = None) -> dict:
    """将 JD 文本结构化为 JDStructured。"""
    llm = llm or LLMService()
    messages = [
        {
            "role": "system",
            "content": "你是招聘信息结构化专家。请把岗位 JD 提取为结构化 JSON，缺失字段留空。",
        },
        {"role": "user", "content": text[:20000]},
    ]
    return llm.complete_structured(messages, JDStructured)
```

- [ ] **Step 4: 创建 `app/services/jd_service.py`**

```python
import json

from sqlalchemy.orm import Session

from app.agents.jd_agent import structure_jd_text
from app.llm import LLMService
from app.models import JD
from app.tools.jd_fetcher import fetch_url_text
from app.vector_store import COLLECTION_JDS, VectorStore


def _store_jd(db: Session, jd: JD, vector_store: VectorStore) -> JD:
    db.add(jd)
    db.commit()
    db.refresh(jd)
    vector_store.add(
        COLLECTION_JDS,
        [json.dumps(jd.structured_json, ensure_ascii=False)],
        [jd.id],
        [{"jd_id": jd.id}],
    )
    return jd


def create_jd_from_text(
    db: Session,
    text: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> JD:
    structured = structure_jd_text(text, llm)
    jd = JD(
        source_type="text",
        raw_text=text,
        company=structured.get("company", ""),
        title=structured.get("title", ""),
        structured_json=structured,
    )
    return _store_jd(db, jd, vector_store)


def create_jd_from_url(
    db: Session,
    url: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> JD:
    text = fetch_url_text(url)
    structured = structure_jd_text(text, llm)
    jd = JD(
        source_type="url",
        source_url=url,
        raw_text=text,
        company=structured.get("company", ""),
        title=structured.get("title", ""),
        structured_json=structured,
    )
    return _store_jd(db, jd, vector_store)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_jd_service.py -v`
Expected: 2 passed

- [ ] **Step 6: 提交**

```bash
git add app/agents/jd_agent.py app/services/jd_service.py tests/test_jd_service.py
git commit -m "feat: JD 智能体与服务（文本/URL）"
```

---

## Milestone D：匹配引擎

### Task 10: LangGraph 匹配工作流（规则 → LLM 打分 → 差距）

**Files:**
- Create: `app/workflow/__init__.py`
- Create: `app/workflow/graph.py`
- Test: `tests/test_match_workflow.py`

- [ ] **Step 1: 写失败测试 `tests/test_match_workflow.py`**

```python
from app.workflow.graph import _extract_terms, build_match_graph


class FakeLLM:
    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(
            {
                "skill_match": 90.0,
                "experience_match": 80.0,
                "education_match": 70.0,
                "hard_requirements": 85.0,
                "reasons": {"skill_match": "技能重合度高"},
                "gaps": ["缺少企业级项目经验", "缺少企业级项目经验"],
                "summary": "整体匹配",
            }
        ).model_dump()


def test_match_graph_full_flow():
    graph = build_match_graph(FakeLLM())
    state = {
        "resume_text": '{"skills": ["Python", "LangGraph"]}',
        "jd_text": '{"requirements": ["Python"]}',
    }
    result = graph.invoke(state)
    assert result["total_score"] == 83.0  # 90*0.35 + 80*0.3 + 70*0.15 + 85*0.2
    assert result["gaps"] == ["缺少企业级项目经验"]  # 去重
    assert result["dimension_scores"]["skill_match"] == 90.0
    assert result["summary"] == "整体匹配"


def test_extract_terms():
    assert _extract_terms("Python, LangGraph 与 MySQL") == {"Python", "LangGraph", "MySQL"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_match_workflow.py -v`
Expected: FAIL（`ModuleNotFoundError: app.workflow.graph`）

- [ ] **Step 3: 创建 `app/workflow/__init__.py`（空文件）与 `app/workflow/graph.py`**

```python
import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


class MatchState(TypedDict, total=False):
    resume_text: str
    jd_text: str
    keyword_overlap: float
    dimension_scores: dict
    reasons: dict
    total_score: float
    gaps: list
    summary: str


class MatchScoring(BaseModel):
    skill_match: float = 0.0
    experience_match: float = 0.0
    education_match: float = 0.0
    hard_requirements: float = 0.0
    reasons: dict[str, str] = {}
    gaps: list[str] = []
    summary: str = ""


WEIGHTS = {
    "skill_match": 0.35,
    "experience_match": 0.30,
    "education_match": 0.15,
    "hard_requirements": 0.20,
}


def _extract_terms(text: str) -> set[str]:
    """提取 ASCII 技能词（Python/LangGraph/MySQL 等）。中文语义由 LLM 打分层处理。"""
    return set(re.findall(r"[A-Za-z0-9][A-Za-z0-9+#._-]{1,}", text))


def build_match_graph(llm):
    def rule_node(state: MatchState) -> MatchState:
        resume_terms = _extract_terms(state["resume_text"])
        jd_terms = _extract_terms(state["jd_text"])
        overlap = round(len(resume_terms & jd_terms) / max(len(jd_terms), 1), 2)
        return {"keyword_overlap": overlap}

    def score_node(state: MatchState) -> MatchState:
        prompt = (
            "你是资深招聘匹配专家。根据简历和 JD 判断匹配度，输出 JSON。\n"
            f"简历：{state['resume_text'][:8000]}\n"
            f"JD：{state['jd_text'][:8000]}\n"
            f"规则层关键词重叠率：{state.get('keyword_overlap', 0)}\n"
            "评分维度 skill_match(技能匹配)/experience_match(经历相关)/"
            "education_match(教育背景)/hard_requirements(硬性条件)，每项 0-100。\n"
            "gaps 给出可行动差距建议（中文，最多 3 条）；summary 用一句话总结匹配度。"
        )
        data = llm.complete_structured([{"role": "user", "content": prompt}], MatchScoring)
        total = round(sum(data[k] * WEIGHTS[k] for k in WEIGHTS), 1)
        return {
            "dimension_scores": {k: data[k] for k in WEIGHTS},
            "reasons": data["reasons"],
            "total_score": total,
            "gaps": data["gaps"],
            "summary": data["summary"],
        }

    def gap_node(state: MatchState) -> MatchState:
        gaps = list(dict.fromkeys(state.get("gaps", [])))[:3]
        return {"gaps": gaps}

    graph = StateGraph(MatchState)
    graph.add_node("rule", rule_node)
    graph.add_node("score", score_node)
    graph.add_node("gaps", gap_node)
    graph.add_edge(START, "rule")
    graph.add_edge("rule", "score")
    graph.add_edge("score", "gaps")
    graph.add_edge("gaps", END)
    return graph.compile()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_match_workflow.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add app/workflow tests/test_match_workflow.py
git commit -m "feat: LangGraph 匹配工作流（规则/打分/差距）"
```

### Task 11: 匹配服务（编排 + 持久化）

**Files:**
- Create: `app/services/match_service.py`
- Test: `tests/test_match_service.py`

- [ ] **Step 1: 写失败测试 `tests/test_match_service.py`**

```python
from app.models import JD, Match, Resume
from app.services.match_service import run_match


class FakeLLM:
    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(
            {
                "skill_match": 90.0,
                "experience_match": 80.0,
                "education_match": 70.0,
                "hard_requirements": 85.0,
                "reasons": {"skill_match": "技能重合度高"},
                "gaps": ["缺少企业级项目经验"],
                "summary": "整体匹配",
            }
        ).model_dump()


def test_run_match_persists(db_session, vector_store):
    resume = Resume(
        raw_text="r",
        structured_json={"skills": ["Python"]},
        status="confirmed",
    )
    jd = JD(
        company="京东",
        title="实习生",
        raw_text="j",
        structured_json={"requirements": ["Python"]},
    )
    db_session.add_all([resume, jd])
    db_session.commit()

    result = run_match(db_session, resume.id, jd.id, vector_store, llm=FakeLLM())
    match = db_session.get(Match, result.match_id)
    assert match.total_score == 83.0
    assert match.dimension_scores_json["skill_match"] == 90.0
    assert match.gaps_json == ["缺少企业级项目经验"]
    assert result.dimension_scores.skill_match == 90.0


def test_run_match_missing_resume_raises(db_session, vector_store):
    import pytest

    with pytest.raises(KeyError):
        run_match(db_session, "nope", "nope", vector_store, llm=FakeLLM())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_match_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.match_service`）

- [ ] **Step 3: 创建 `app/services/match_service.py`**

```python
import json

from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import JD, Match, Resume
from app.schemas import DimensionScores, MatchResult
from app.vector_store import VectorStore
from app.workflow.graph import build_match_graph


def run_match(
    db: Session,
    resume_id: str,
    jd_id: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> MatchResult:
    resume = db.get(Resume, resume_id)
    jd = db.get(JD, jd_id)
    if resume is None:
        raise KeyError(f"resume not found: {resume_id}")
    if jd is None:
        raise KeyError(f"jd not found: {jd_id}")

    graph = build_match_graph(llm)
    state = {
        "resume_text": json.dumps(resume.structured_json, ensure_ascii=False),
        "jd_text": json.dumps(jd.structured_json, ensure_ascii=False),
    }
    result = graph.invoke(state)

    match = Match(
        resume_id=resume_id,
        jd_id=jd_id,
        dimension_scores_json=result["dimension_scores"],
        total_score=result["total_score"],
        gaps_json=result["gaps"],
        summary=result["summary"],
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return MatchResult(
        match_id=match.id,
        jd_id=jd_id,
        dimension_scores=DimensionScores(**result["dimension_scores"]),
        reasons=result["reasons"],
        total_score=result["total_score"],
        gaps=result["gaps"],
        summary=result["summary"],
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_match_service.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add app/services/match_service.py tests/test_match_service.py
git commit -m "feat: 匹配服务与 Match 持久化"
```

---

## Milestone E：自荐信

### Task 12: 自荐信服务（草稿 + judge 自检循环）

**Files:**
- Create: `app/services/cover_letter_service.py`
- Test: `tests/test_cover_letter.py`

- [ ] **Step 1: 写失败测试 `tests/test_cover_letter.py`**

```python
from app.models import JD, Match, Resume
from app.services.cover_letter_service import generate_cover_letter


class FakeLLM:
    def __init__(self, drafts, judge_scores):
        self.drafts = drafts
        self.judge_scores = judge_scores
        self.draft_calls = 0

    def complete(self, messages, max_tokens=2000):
        draft = self.drafts[min(self.draft_calls, len(self.drafts) - 1)]
        self.draft_calls += 1
        return draft

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(
            {"score": self.judge_scores.pop(0), "feedback": "ok"}
        ).model_dump()


def _setup(db_session):
    resume = Resume(raw_text="r", structured_json={"name": "张三"}, status="confirmed")
    jd = JD(
        company="京东",
        title="实习生",
        raw_text="j",
        structured_json={"requirements": ["Python"]},
    )
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(
        resume_id=resume.id,
        jd_id=jd.id,
        total_score=80.0,
        dimension_scores_json={"skill_match": 90.0},
        gaps_json=["缺少企业级项目经验"],
    )
    db_session.add(match)
    db_session.commit()
    return match.id


def test_generate_cover_letter_revises_when_score_low(db_session):
    match_id = _setup(db_session)
    llm = FakeLLM(drafts=["第一版", "第二版"], judge_scores=[0.5, 0.9])
    result = generate_cover_letter(db_session, match_id, "standard", llm=llm)
    assert result["content"] == "第二版"
    assert result["revised"] is True
    assert result["judge_score"] == 0.9
    assert llm.draft_calls == 2


def test_generate_cover_letter_no_revision_when_score_ok(db_session):
    match_id = _setup(db_session)
    llm = FakeLLM(drafts=["很好的一版"], judge_scores=[0.92])
    result = generate_cover_letter(db_session, match_id, "concise", llm=llm)
    assert result["content"] == "很好的一版"
    assert result["revised"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cover_letter.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.cover_letter_service`）

- [ ] **Step 3: 创建 `app/services/cover_letter_service.py`**

```python
import json

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import JD, Match, Resume


class JudgeScore(BaseModel):
    score: float = 0.0
    feedback: str = ""


COVER_LETTER_TONES = {
    "standard": "语气专业平实",
    "warm": "语气热情有感染力",
    "concise": "内容精炼、要点突出",
}


def generate_cover_letter(
    db: Session,
    match_id: str,
    tone: str = "standard",
    llm: LLMService | None = None,
) -> dict:
    llm = llm or LLMService()
    match = db.get(Match, match_id)
    if match is None:
        raise KeyError(f"match not found: {match_id}")
    resume = db.get(Resume, match.resume_id)
    jd = db.get(JD, match.jd_id)
    if resume is None or jd is None:
        raise KeyError("resume or jd not found")

    tone_desc = COVER_LETTER_TONES.get(tone, COVER_LETTER_TONES["standard"])
    draft = _draft(resume, jd, match, tone_desc, llm, feedback=None)
    score = _judge(draft, jd, llm)
    revised = False
    if score < 0.8:
        draft = _draft(
            resume,
            jd,
            match,
            tone_desc,
            llm,
            feedback=f"上一版质量分 {score:.2f}，请改进后重新生成。",
        )
        score = _judge(draft, jd, llm)
        revised = True
    return {"content": draft, "judge_score": score, "revised": revised}


def _draft(resume: Resume, jd: JD, match: Match, tone_desc: str, llm: LLMService, feedback: str | None) -> str:
    prompt = (
        f"请写一封求职自荐信（{tone_desc}），300-400 字。\n"
        f"候选人：{json.dumps(resume.structured_json, ensure_ascii=False)}\n"
        f"岗位：{jd.company} {jd.title}\n"
        f"JD 要点：{json.dumps(jd.structured_json, ensure_ascii=False)}\n"
        f"匹配总分 {match.total_score}，维度分 {match.dimension_scores_json}，差距 {match.gaps_json}\n"
        "写作要求：开头点明申请意向；正文用 2-3 个与 JD 直接相关的经历/项目亮点（尽量量化）；"
        "如有明显差距，用一句学习意愿或迁移能力补强；结尾礼貌收束。"
    )
    if feedback:
        prompt += f"\n评审反馈：{feedback}"
    return llm.complete([{"role": "user", "content": prompt}])


def _judge(draft: str, jd: JD, llm: LLMService) -> float:
    prompt = (
        "你是自荐信评审。按 rubric 打分（0-1 分，保留两位小数）：\n"
        "1) 覆盖 JD 关键要求 2) 有量化成果 3) 结构完整（开头-正文-结尾）4) 语言得体\n"
        f"JD：{json.dumps(jd.structured_json, ensure_ascii=False)}\n"
        f"自荐信：\n{draft}\n"
        '输出 JSON：{"score": 0.0-1.0, "feedback": "改进建议"}'
    )
    data = llm.complete_structured([{"role": "user", "content": prompt}], JudgeScore)
    return float(data["score"])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_cover_letter.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add app/services/cover_letter_service.py tests/test_cover_letter.py
git commit -m "feat: 自荐信生成与 judge 自检循环"
```

---

## Milestone F：API 与 SSE

### Task 13: 事件总线（SSE 用）

**Files:**
- Create: `app/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: 写失败测试 `tests/test_events.py`**

```python
from app.events import EventBus


def test_publish_subscribe_and_unsubscribe():
    bus = EventBus()
    q = bus.subscribe("t1")
    bus.publish("t1", {"type": "started"})
    assert q.get(timeout=1)["type"] == "started"
    bus.unsubscribe("t1", q)
    assert "t1" not in bus._queues


def test_multiple_subscribers():
    bus = EventBus()
    q1 = bus.subscribe("t1")
    q2 = bus.subscribe("t1")
    bus.publish("t1", {"type": "x"})
    assert q1.get(timeout=1)["type"] == "x"
    assert q2.get(timeout=1)["type"] == "x"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_events.py -v`
Expected: FAIL（`ModuleNotFoundError: app.events`）

- [ ] **Step 3: 创建 `app/events.py`**

```python
import queue
from typing import Any


class EventBus:
    """线程安全事件总线：后台任务发布事件，SSE 生成器订阅。"""

    def __init__(self):
        self._queues: dict[str, list[queue.Queue]] = {}

    def publish(self, task_id: str, event: dict[str, Any]) -> None:
        for q in self._queues.get(task_id, []):
            q.put(event)

    def subscribe(self, task_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        self._queues.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        if task_id in self._queues and q in self._queues[task_id]:
            self._queues[task_id].remove(q)
            if not self._queues[task_id]:
                del self._queues[task_id]


event_bus = EventBus()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_events.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add app/events.py tests/test_events.py
git commit -m "feat: 线程安全事件总线"
```

### Task 14: FastAPI 端点与 SSE 流

**Files:**
- Create: `app/main.py`
- Test: `tests/test_api.py`
- Modify: `tests/conftest.py`（追加 client fixture）

- [ ] **Step 1: 在 `tests/conftest.py` 末尾追加 client fixture**

```python
from fastapi.testclient import TestClient

from fixtures_data import RESUME_DATA


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
        return schema.model_validate({**self.structured}).model_dump()


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
```

- [ ] **Step 2: 写失败测试 `tests/test_api.py`**

```python
import threading
import time

import fitz

from app.events import event_bus


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_upload_then_confirm_flow(client, tmp_path):
    pdf_path = tmp_path / "r.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "姓名：张三")
    doc.save(str(pdf_path))
    doc.close()

    with open(pdf_path, "rb") as f:
        res = client.post(
            "/api/resume/upload",
            files={"file": ("r.pdf", f, "application/pdf")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending_confirmation"
    assert data["structured"]["name"] == "张三"

    res2 = client.post(
        f"/api/resume/{data['resume_id']}/confirm",
        json={"structured": data["structured"]},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "confirmed"


def test_create_jd_text(client):
    res = client.post("/api/jds", json={"source": "text", "text": "京东招聘 LLM 应用开发实习生"})
    assert res.status_code == 200
    data = res.json()
    assert data["company"] == "京东"
    assert data["title"] == "LLM 应用开发实习生"


def test_create_jd_url_requires_url(client):
    res = client.post("/api/jds", json={"source": "url", "url": ""})
    assert res.status_code == 400


def test_create_match_returns_task_id(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "run_matches_task", lambda *a, **k: None)
    res = client.post("/api/matches", json={"resume_id": "r1", "jd_ids": ["j1"]})
    assert res.status_code == 200
    assert "task_id" in res.json()


def test_cover_letter_missing_match_returns_404(client):
    res = client.post(
        "/api/matches/missing/cover-letter",
        json={"match_id": "missing", "tone": "standard"},
    )
    assert res.status_code == 404


def test_sse_stream_delivers_completed_event(client):
    task_id = "sse-test-1"

    def pub():
        time.sleep(0.2)
        event_bus.publish(task_id, {"type": "completed"})

    threading.Thread(target=pub, daemon=True).start()
    with client.stream("GET", f"/api/matches/{task_id}/stream") as response:
        body = b"".join(response.iter_bytes()).decode()
    assert "completed" in body
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_api.py -v`
Expected: FAIL（`ModuleNotFoundError: app.main`）

- [ ] **Step 4: 创建 `app/main.py`**

```python
import asyncio
import json
import queue as queue_module
import threading
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.db import SessionLocal, get_session
from app.events import event_bus
from app.llm import LLMService
from app.schemas import CoverLetterRequest, MatchRequest
from app.services import cover_letter_service, jd_service, match_service, resume_service
from app.vector_store import VectorStore

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

vector_store = VectorStore()
llm = LLMService()


@app.on_event("startup")
def on_startup() -> None:
    from app.db import Base, engine

    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/resume/upload")
def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_session)):
    suffix = Path(file.filename or "resume.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    file_path.write_bytes(file.file.read())
    try:
        resume = resume_service.create_resume_from_file(db, str(file_path), vector_store, llm=llm)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"简历解析失败: {exc}") from exc
    return {
        "resume_id": resume.id,
        "status": resume.status,
        "structured": resume.structured_json,
    }


@app.post("/api/resume/{resume_id}/confirm")
def confirm_resume(resume_id: str, payload: dict, db: Session = Depends(get_session)):
    try:
        resume = resume_service.confirm_resume(
            db, resume_id, payload.get("structured", {}), vector_store
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"resume_id": resume.id, "status": resume.status}


@app.post("/api/jds")
def create_jd(payload: dict, db: Session = Depends(get_session)):
    source = payload.get("source", "text")
    if source == "url":
        url = payload.get("url", "")
        if not url:
            raise HTTPException(status_code=400, detail="url 必填")
        try:
            jd = jd_service.create_jd_from_url(db, url, vector_store, llm=llm)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"JD 抓取失败: {exc}") from exc
    else:
        text = payload.get("text", "")
        if not text.strip():
            raise HTTPException(status_code=400, detail="text 必填")
        jd = jd_service.create_jd_from_text(db, text, vector_store, llm=llm)
    return {
        "jd_id": jd.id,
        "company": jd.company,
        "title": jd.title,
        "structured": jd.structured_json,
    }


def run_matches_task(task_id: str, resume_id: str, jd_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        event_bus.publish(task_id, {"type": "started", "total": len(jd_ids)})
        for index, jd_id in enumerate(jd_ids):
            event_bus.publish(
                task_id,
                {"type": "match_progress", "index": index, "total": len(jd_ids), "jd_id": jd_id},
            )
            result = match_service.run_match(db, resume_id, jd_id, vector_store, llm=llm)
            event_bus.publish(task_id, {"type": "match_result", "result": result.model_dump()})
        event_bus.publish(task_id, {"type": "completed"})
    except Exception as exc:
        event_bus.publish(task_id, {"type": "error", "message": str(exc)})
    finally:
        db.close()


@app.post("/api/matches")
def create_match(payload: MatchRequest):
    task_id = uuid.uuid4().hex
    threading.Thread(
        target=run_matches_task,
        args=(task_id, payload.resume_id, payload.jd_ids),
        daemon=True,
    ).start()
    return {"task_id": task_id}


@app.get("/api/matches/{task_id}/stream")
async def match_stream(task_id: str):
    q = event_bus.subscribe(task_id)

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.to_thread(q.get, True, 0.5)
                except queue_module.Empty:
                    continue
                yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
                if event["type"] in ("completed", "error"):
                    break
        finally:
            event_bus.unsubscribe(task_id, q)

    return EventSourceResponse(gen())


@app.post("/api/matches/{match_id}/cover-letter")
def cover_letter(match_id: str, payload: CoverLetterRequest, db: Session = Depends(get_session)):
    try:
        result = cover_letter_service.generate_cover_letter(db, match_id, payload.tone, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


web_dist = Path(__file__).resolve().parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
```

- [ ] **Step 5: 运行全部测试**

Run: `pytest tests/ -v`
Expected: 全部通过（当前约 22 个用例）

- [ ] **Step 6: 提交**

```bash
git add app/main.py tests/test_api.py tests/conftest.py
git commit -m "feat: FastAPI 端点与 SSE 匹配进度流"
```

---

## Milestone G：前端

### Task 15: Vite + React + Tailwind 骨架

**Files:**
- Create: `app/web/package.json`
- Create: `app/web/vite.config.js`
- Create: `app/web/tailwind.config.js`
- Create: `app/web/postcss.config.js`
- Create: `app/web/index.html`
- Create: `app/web/src/main.jsx`
- Create: `app/web/src/index.css`

- [ ] **Step 1: 创建 `app/web/package.json`**

```json
{
  "name": "job-copilot-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.4",
    "vite": "^5.3.0"
  }
}
```

- [ ] **Step 2: 创建 `app/web/vite.config.js`**

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  },
  build: {
    outDir: 'dist'
  }
})
```

- [ ] **Step 3: 创建 `app/web/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {}
  },
  plugins: []
}
```

- [ ] **Step 4: 创建 `app/web/postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {}
  }
}
```

- [ ] **Step 5: 创建 `app/web/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Job Copilot</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 6: 创建 `app/web/src/main.jsx` 与 `app/web/src/index.css`**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: 安装依赖并验证构建**

Run: `cd app/web && npm install && npm run build`
Expected: `dist/` 目录生成，构建无报错（此时 App.jsx 尚不存在，先创建占位 `src/App.jsx` 即可；也可延后到 Task 18 一并验证）

> 说明：为让本任务可独立验证，先创建最小 `src/App.jsx`：

```jsx
export default function App() {
  return <div className="p-6">Job Copilot</div>
}
```

- [ ] **Step 8: 提交**

```bash
git add app/web
git commit -m "feat: Vite + React + Tailwind 前端骨架"
```

### Task 16: API 客户端与简历面板

**Files:**
- Create: `app/web/src/api.js`
- Create: `app/web/src/components/ResumePanel.jsx`

- [ ] **Step 1: 创建 `app/web/src/api.js`**

```js
async function parseError(res) {
  try {
    return (await res.json()).detail || res.statusText
  } catch {
    return res.statusText
  }
}

export async function uploadResume(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/resume/upload', { method: 'POST', body: form })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function confirmResume(resumeId, structured) {
  const res = await fetch(`/api/resume/${resumeId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ structured })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createJD(payload) {
  const res = await fetch('/api/jds', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function runMatch(resumeId, jdIds) {
  const res = await fetch('/api/matches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id: resumeId, jd_ids: jdIds })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function generateCoverLetter(matchId, tone) {
  const res = await fetch(`/api/matches/${matchId}/cover-letter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ match_id: matchId, tone })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
```

- [ ] **Step 2: 创建 `app/web/src/components/ResumePanel.jsx`**

```jsx
import { useState } from 'react'
import { confirmResume, uploadResume } from '../api.js'

export default function ResumePanel({ onResumeReady }) {
  const [file, setFile] = useState(null)
  const [uploadedId, setUploadedId] = useState('')
  const [edited, setEdited] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const handleUpload = async () => {
    if (!file) return
    setBusy(true)
    setMessage('')
    try {
      const data = await uploadResume(file)
      setUploadedId(data.resume_id)
      setEdited(JSON.stringify(data.structured, null, 2))
      setMessage('解析完成，请核对下方结构化结果后确认')
    } catch (e) {
      setMessage(`解析失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleConfirm = async () => {
    let structured
    try {
      structured = JSON.parse(edited)
    } catch {
      setMessage('结构化结果不是合法 JSON，请修正后再确认')
      return
    }
    setBusy(true)
    try {
      await confirmResume(uploadedId, structured)
      onResumeReady(uploadedId)
      setMessage('已确认并入库，可以开始录入 JD 了')
    } catch (e) {
      setMessage(`确认失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-end">
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files[0])}
          className="text-sm"
        />
        <button
          onClick={handleUpload}
          disabled={busy || !file}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
        >
          {busy ? '解析中…' : '上传并解析'}
        </button>
      </div>
      {message && <p className="text-sm text-slate-600">{message}</p>}
      {edited && (
        <div className="space-y-3">
          <textarea
            value={edited}
            onChange={(e) => setEdited(e.target.value)}
            rows={18}
            className="w-full font-mono text-xs border rounded-lg p-3"
          />
          <button
            onClick={handleConfirm}
            disabled={busy || !uploadedId}
            className="px-4 py-2 bg-green-600 text-white rounded-lg disabled:opacity-50"
          >
            确认并入库
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add app/web/src/api.js app/web/src/components
git commit -m "feat: 前端 API 客户端与简历面板"
```

### Task 17: JD 面板与匹配面板（SSE 进度）

**Files:**
- Create: `app/web/src/components/JDPanel.jsx`
- Create: `app/web/src/components/MatchPanel.jsx`

- [ ] **Step 1: 创建 `app/web/src/components/JDPanel.jsx`**

```jsx
import { useState } from 'react'
import { createJD } from '../api.js'

export default function JDPanel({ onJDAdded }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const handleAdd = async () => {
    setBusy(true)
    setMessage('')
    try {
      const payload = mode === 'url' ? { source: 'url', url } : { source: 'text', text }
      const data = await createJD(payload)
      onJDAdded(data.jd_id)
      setMessage(`已录入：${data.company} ${data.title}（${data.jd_id}）`)
      setText('')
      setUrl('')
    } catch (e) {
      setMessage(`录入失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const tabClass = (active) =>
    `px-4 py-2 rounded-lg text-sm ${active ? 'bg-blue-600 text-white' : 'bg-slate-100 hover:bg-slate-200'}`

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button onClick={() => setMode('text')} className={tabClass(mode === 'text')}>
          粘贴文本
        </button>
        <button onClick={() => setMode('url')} className={tabClass(mode === 'url')}>
          URL 抓取
        </button>
      </div>
      {mode === 'text' ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          placeholder="粘贴 JD 全文"
          className="w-full border rounded-lg p-3 text-sm"
        />
      ) : (
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          className="w-full border rounded-lg p-3 text-sm"
        />
      )}
      <button
        onClick={handleAdd}
        disabled={busy || (mode === 'text' ? !text.trim() : !url.trim())}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
      >
        {busy ? '录入中…' : '录入 JD'}
      </button>
      {message && <p className="text-sm text-slate-600">{message}</p>}
    </div>
  )
}
```

- [ ] **Step 2: 创建 `app/web/src/components/MatchPanel.jsx`**

```jsx
import { useState } from 'react'
import { generateCoverLetter, runMatch } from '../api.js'

export default function MatchPanel({ resumeId, jdIds }) {
  const [extraIds, setExtraIds] = useState('')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState('')
  const [results, setResults] = useState([])
  const [cover, setCover] = useState(null)
  const [busyId, setBusyId] = useState('')
  const [tone, setTone] = useState('standard')

  const handleMatch = async () => {
    const ids = [...jdIds, ...extraIds.split(',').map((s) => s.trim()).filter(Boolean)]
    if (!resumeId || ids.length === 0) {
      setProgress('请先确认简历并录入至少一个 JD')
      return
    }
    setBusy(true)
    setResults([])
    setCover(null)
    setProgress('发起匹配…')
    try {
      const { task_id } = await runMatch(resumeId, ids)
      const es = new EventSource(`/api/matches/${task_id}/stream`)
      es.addEventListener('match_progress', (e) => {
        const d = JSON.parse(e.data)
        setProgress(`正在匹配 ${d.index + 1}/${d.total}…`)
      })
      es.addEventListener('match_result', (e) => {
        const d = JSON.parse(e.data)
        setResults((prev) => [...prev, d.result])
      })
      es.addEventListener('completed', () => {
        setProgress('匹配完成')
        setBusy(false)
        es.close()
      })
      es.addEventListener('error', () => {
        setProgress('匹配出错，请检查服务端日志')
        setBusy(false)
        es.close()
      })
    } catch (e) {
      setProgress(`发起匹配失败：${e.message}`)
      setBusy(false)
    }
  }

  const handleCover = async (matchId) => {
    setBusyId(matchId)
    try {
      const data = await generateCoverLetter(matchId, tone)
      setCover({ matchId, ...data })
    } catch (e) {
      setCover({ matchId, content: `生成失败：${e.message}`, judge_score: 0, revised: false })
    } finally {
      setBusyId('')
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border rounded-lg p-4 text-sm space-y-2">
        <p>简历 ID：<span className="font-mono">{resumeId || '（未确认）'}</span></p>
        <p>已录入 JD：{jdIds.length === 0 ? '（无）' : jdIds.map((id) => <span key={id} className="inline-block bg-slate-100 rounded px-2 py-0.5 mr-1 font-mono text-xs">{id}</span>)}</p>
        <input
          value={extraIds}
          onChange={(e) => setExtraIds(e.target.value)}
          placeholder="补充 JD ID（逗号分隔，可选）"
          className="w-full border rounded-lg p-2 text-sm"
        />
        <div className="flex gap-2 items-center">
          <select value={tone} onChange={(e) => setTone(e.target.value)} className="border rounded-lg p-2 text-sm">
            <option value="standard">自荐信语气：标准</option>
            <option value="warm">自荐信语气：热情</option>
            <option value="concise">自荐信语气：简洁</option>
          </select>
          <button
            onClick={handleMatch}
            disabled={busy}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
          >
            {busy ? '匹配中…' : '开始匹配'}
          </button>
        </div>
        {progress && <p className="text-slate-600">{progress}</p>}
      </div>

      {results.map((r) => (
        <div key={r.match_id} className="bg-white border rounded-lg p-4 space-y-2">
          <div className="flex justify-between">
            <span className="font-mono text-xs">{r.jd_id}</span>
            <span className="text-lg font-bold text-blue-600">{r.total_score} 分</span>
          </div>
          <p className="text-sm">{r.summary}</p>
          <div className="grid grid-cols-4 gap-2 text-xs">
            {Object.entries(r.dimension_scores).map(([k, v]) => (
              <div key={k} className="bg-slate-50 rounded p-2">
                <div className="text-slate-500">{k}</div>
                <div className="font-semibold">{v}</div>
              </div>
            ))}
          </div>
          {r.gaps.length > 0 && (
            <ul className="text-xs text-slate-600 list-disc pl-4">
              {r.gaps.map((g) => <li key={g}>{g}</li>)}
            </ul>
          )}
          <button
            onClick={() => handleCover(r.match_id)}
            disabled={busyId === r.match_id}
            className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50"
          >
            {busyId === r.match_id ? '生成中…' : '生成自荐信'}
          </button>
        </div>
      ))}

      {cover && (
        <div className="bg-white border rounded-lg p-4 space-y-2">
          <div className="text-sm text-slate-600">
            match {cover.matchId} · 评审分 {cover.judge_score} {cover.revised ? '· 已按评审重写' : ''}
          </div>
          <pre className="whitespace-pre-wrap text-sm bg-slate-50 rounded-lg p-4">{cover.content}</pre>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add app/web/src/components
git commit -m "feat: JD 面板与匹配面板（SSE 进度）"
```

### Task 18: 应用外壳（Tab 导航 + 状态提升）

**Files:**
- Modify: `app/web/src/App.jsx`（替换 Task 15 的占位实现）

- [ ] **Step 1: 替换 `app/web/src/App.jsx`**

```jsx
import { useState } from 'react'
import JDPanel from './components/JDPanel.jsx'
import MatchPanel from './components/MatchPanel.jsx'
import ResumePanel from './components/ResumePanel.jsx'

const TABS = [
  { key: 'resume', label: '简历', component: ResumePanel },
  { key: 'jd', label: '岗位 JD', component: JDPanel },
  { key: 'match', label: '匹配与自荐信', component: MatchPanel }
]

export default function App() {
  const [active, setActive] = useState('resume')
  const [resumeId, setResumeId] = useState(localStorage.getItem('jc_resume_id') || '')
  const [jdIds, setJdIds] = useState(JSON.parse(localStorage.getItem('jc_jd_ids') || '[]'))

  const handleResumeReady = (id) => {
    setResumeId(id)
    localStorage.setItem('jc_resume_id', id)
  }

  const handleJDAdded = (id) => {
    const next = [...jdIds, id]
    setJdIds(next)
    localStorage.setItem('jc_jd_ids', JSON.stringify(next))
  }

  const ActiveComponent = TABS.find((t) => t.key === active).component

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-bold">Job Copilot</h1>
        <p className="text-sm text-slate-500">求职全生命周期 Agent · Phase 1 核心闭环</p>
      </header>
      <nav className="flex gap-2 px-6 py-3 bg-white border-b">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`px-4 py-2 rounded-lg text-sm ${
              active === t.key ? 'bg-blue-600 text-white' : 'bg-slate-100 hover:bg-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <main className="p-6 max-w-4xl">
        <ActiveComponent
          resumeId={resumeId}
          jdIds={jdIds}
          onResumeReady={handleResumeReady}
          onJDAdded={handleJDAdded}
        />
      </main>
    </div>
  )
}
```

- [ ] **Step 2: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交**

```bash
git add app/web/src/App.jsx
git commit -m "feat: 应用外壳与跨面板状态"
```

### Task 19: 前后端联调（静态托管 + 开发代理）

**Files:**
- Modify: 无（`app/main.py` 已在 Task 14 内置静态托管；`app/web/vite.config.js` 已配置代理）

- [ ] **Step 1: 启动后端并做冒烟验证**

Run（项目根目录）:
```bash
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
另开终端：`curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 2: 构建前端并由 FastAPI 托管**

Run: `cd app/web && npm run build && cd .. && cd .. && uvicorn app.main:app --port 8000`
Expected: 浏览器访问 `http://localhost:8000/` 出现 Job Copilot 页面（`dist` 存在时自动挂载）

- [ ] **Step 3: 开发模式联调（热更新）**

Run: `cd app/web && npm run dev`（保持后端在 8000 端口）
Expected: `http://localhost:5173` 可访问，`/api` 请求经代理转发到后端

- [ ] **Step 4: 提交（如无改动则跳过）**

```bash
git status
```
Expected: 无未提交改动（本任务无代码变更）

---

## Milestone H：工程化与验收

### Task 20: Docker 化

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: 创建 `Dockerfile`（多阶段：先构建前端，再打包后端）**

```dockerfile
FROM node:20-slim AS web
WORKDIR /web
COPY app/web/package.json app/web/package-lock.json* ./
RUN npm install
COPY app/web .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY --from=web /web/dist ./app/web/dist
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
```

- [ ] **Step 3: 验证镜像构建与启动**

Run: `docker compose up --build`
Expected: 容器启动，`http://localhost:8000/health` 返回 `{"status":"ok"}`，首页可访问

- [ ] **Step 4: 提交**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: Docker 化部署"
```

### Task 21: CI（pytest + 覆盖率）

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: 创建 `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov httpx
      - name: Run tests with coverage
        run: pytest tests/ --cov=app --cov-report=term-missing
```

- [ ] **Step 2: 本地模拟 CI**

Run: `pytest tests/ --cov=app --cov-report=term-missing`
Expected: 全部通过，覆盖率报告输出

- [ ] **Step 3: 提交**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: 添加测试与覆盖率流水线"
```

### Task 22: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 `README.md`**

```markdown
# Job Copilot

一站式求职 Agent：上传简历 → 结构化确认 → 录入 JD → 匹配打分 → 生成自荐信。

## 功能（Phase 1）

- 简历 PDF 解析与 LLM 结构化（人工确认后入库）
- JD 多来源录入（粘贴文本 / URL 抓取）
- 四维可解释匹配打分 + 差距分析（LangGraph 工作流）
- 自荐信生成 + LLM-as-judge 自检重写
- SSE 实时匹配进度

## 快速开始

### 后端

```bash
cp .env.example .env   # 填入 LLM_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端（开发模式）

```bash
cd app/web
npm install
npm run dev            # http://localhost:5173，/api 自动代理到 8000
```

### Docker

```bash
cp .env.example .env
docker compose up --build
```

## 测试

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```

## 架构

FastAPI + LangGraph + ChromaDB + SQLite + React（详见 `docs/superpowers/specs/2026-08-04-job-copilot-design.md`）。
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: README 快速开始"
```

### Task 23: 端到端验收清单

**Files:** 无（人工验收）

- [ ] **Step 1: 环境就绪**

Run: `pytest tests/ -v`
Expected: 全部通过（约 25 个用例）

- [ ] **Step 2: 完整主闭环人工走查**

1. 启动后端（`uvicorn app.main:app --reload --port 8000`），前端 `npm run dev`。
2. 上传一份真实简历 PDF → 看到结构化 JSON → 点击「确认并入库」。
3. 粘贴一条真实 JD 文本 → 看到结构化后的公司/岗位。
4. 进入「匹配与自荐信」→ 点击「开始匹配」→ 看到 SSE 进度逐条推进 → 出现四维分数与差距。
5. 点击「生成自荐信」→ 看到自荐信全文与评审分。

Expected: 5 步全部可完成，无报错。

- [ ] **Step 3: 错误路径走查**

1. 上传非 PDF 文件 → 400「仅支持 PDF 文件」。
2. URL 来源留空 → 400「url 必填」。
3. 自荐信请求不存在的 match_id → 404。

Expected: 3 条错误路径返回预期状态码与提示。

- [ ] **Step 4: Docker 走查**

Run: `docker compose up --build`
Expected: 容器内同走一遍 Step 2 的主闭环。

- [ ] **Step 5: 收尾提交（如有修复）**

```bash
git add -A
git commit -m "fix: 验收修复"
```

---

## 自检记录

### 1. Spec 覆盖

| 设计文档要求 | 对应任务 |
|------------|---------|
| 项目骨架 / Docker / CI | Task 1、20、21 |
| 简历智能体（解析+结构化+人工确认） | Task 7、8、14 |
| 匹配引擎（四维打分+差距分析） | Task 10、11 |
| 自荐信（带自检闭环） | Task 12 |
| SSE 实时进度 | Task 13、14 |
| 基础前端（简历/JD/匹配/自荐信） | Task 15–19 |
| 错误处理（非 PDF、缺参数、404、URL 抓取失败） | Task 14 端点校验 + Task 23 错误路径 |

Phase 2+ 内容（Supervisor、投递状态机、面试陪练、评测平台、市场洞察）不在本计划，按设计文档第 12 节后续另立计划。

### 2. 占位符扫描

已全文扫描：无 TBD / TODO / 「后续实现」等占位；所有代码步骤均含完整代码。

### 3. 类型与命名一致性

- 四维评分键统一为 `skill_match` / `experience_match` / `education_match` / `hard_requirements`（Task 10 工作流、Task 11 持久化、前端 `Object.entries` 渲染一致）。
- `MatchResult` 字段名（`match_id` / `jd_id` / `dimension_scores` / `total_score` / `gaps` / `summary`）在服务层、API 响应、SSE 事件与前端消费处一致。
- 自荐信响应键（`content` / `judge_score` / `revised`）在服务层与前端 `handleCover` 一致。
- LLM 注入约定统一为 `llm: LLMService | None = None`，全部服务在调用处透传。
- 测试 fixture 名称统一为 `db_session` / `vector_store` / `client`，各测试文件一致使用。
