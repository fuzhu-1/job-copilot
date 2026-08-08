# Job Copilot 审计整改实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/audit-report-2026-08.md` 的 P0/P1 结论，把 Job Copilot 从"单机演示可跑"提升为"工程上可维护、可部署、中文可用"，并保持现有 91 个测试全绿。

**Architecture:** 保留现有分层（API → services → agents/tools/workflow → 存储），不做推倒重来。核心决策：① 用「jieba 分词 + 纯 Python BM25 + SQLite 持久化」替换 ChromaDB 向量库（移除只写不读的死重，同时解决中文检索失效），并新增 JD 关键词搜索消费检索能力；② 后台匹配任务从「线程 + 进程内事件总线」改为「SQLite 任务表 + 事件持久化」，SSE 改为轮询任务表，天然消除竞态且支持多进程；③ LLM 层补超时/退避/JSON 模式/日志；④ 补迁移、锁依赖、CI、golden set 可移植性。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、jieba、openai、pytest；前端 React/Vite（仅 CI 构建改动）；后续阶段可选 ARQ+Redis、Langfuse。

> 说明：本计划覆盖多个子系统，但按你的要求合并为一个分阶段计划。每个阶段都独立可交付、可回滚，执行时建议按阶段逐个推进。
> 执行前置：先建分支 `codex/audit-remediation`（或按 superpowers:using-git-worktrees 建 worktree），每个任务完成后提交一次。

---

## 阶段 0：基线

### Task 0: 记录当前基线

**Files:**
- Modify: `docs/eval-baseline.md`

- [ ] **Step 1: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -q`

Expected: `91 passed`

- [ ] **Step 2: 记录基线并提交**

把本次 run 信息追加到 `docs/eval-baseline.md` 表格（若已有 2026-08-06 行则不改），然后：

```bash
git switch -c codex/audit-remediation
git add docs/eval-baseline.md
git commit -m "chore: 记录审计整改前基线"
```

---

## 阶段 1：中文分词与检索层（报告 P0-1、P0-2、P1-16）

### Task 1: 让 `extract_terms` 支持中文分词

**Files:**
- Modify: `app/utils/text.py`
- Modify: `pyproject.toml`、`requirements.txt`（加 jieba）
- Test: `tests/test_text_utils.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_text_utils.py` 末尾追加：

```python
def test_extract_terms_chinese():
    terms = extract_terms("熟悉 Python，有机器学习项目经验，掌握 MySQL")
    assert "机器学习" in terms
    assert "项目经验" in terms
    assert "的" not in terms  # 单字虚词被过滤
    assert "Python" in terms
    assert "MySQL" in terms
```

注意：双字词（如"熟悉"）此时仍会出现在结果里，停用词过滤在 Task 3 的市场洞察层做；本任务只断言双字词能被提取、单字虚词被过滤。

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_text_utils.py::test_extract_terms_chinese -q`

Expected: FAIL（`"机器学习" not in {...}`）

- [ ] **Step 3: 安装 jieba 并实现**

在 `pyproject.toml` 的 `dependencies` 中加 `"jieba>=0.42.1"`，在 `requirements.txt` 加 `jieba>=0.42.1`，然后执行安装：

```bash
.\.venv\Scripts\python.exe -m pip install "jieba>=0.42.1"
```

将 `app/utils/text.py` 整体替换为：

```python
import re

import jieba

_ASCII_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#._-]{1,}")
_HAS_TEXT_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")


def extract_terms(text: str) -> set[str]:
    """提取技能词：ASCII 词 + jieba 中文分词（双字及以上）。"""
    terms: set[str] = set()
    terms.update(_ASCII_RE.findall(text))
    for word in jieba.cut(text):
        word = word.strip()
        if len(word) >= 2 and _HAS_TEXT_RE.search(word):
            terms.add(word)
    return terms
```

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_text_utils.py -q`

Expected: PASS（原有 `test_extract_terms` 期望 `{"Python", "LangGraph", "MySQL"}` 仍然成立：jieba 切出的 "与" 是单字，被过滤）

- [ ] **Step 5: 提交**

```bash
git add app/utils/text.py tests/test_text_utils.py pyproject.toml requirements.txt
git commit -m "feat: extract_terms 支持 jieba 中文分词"
```

### Task 2: 规则层关键词重叠接入中文

`workflow/graph.py` 的 `_extract_terms` 直接复用 `extract_terms`，Task 1 完成后自动生效，无需改代码。本任务只补测试证明中文重叠率非零。

**Files:**
- Test: `tests/test_match_workflow.py`

- [ ] **Step 1: 写测试**

在 `tests/test_match_workflow.py` 末尾追加：

```python
def test_extract_terms_chinese_overlap():
    resume = '{"skills": ["机器学习", "RAG"], "projects": [{"name": "检索系统"}]}'
    jd = '{"requirements": ["熟悉机器学习", "有 RAG 经验"]}'
    overlap = len(_extract_terms(resume) & _extract_terms(jd)) / len(_extract_terms(jd))
    assert overlap > 0.3  # 中文+ASCII 都能命中，重叠率应显著大于 0
```

- [ ] **Step 2: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_match_workflow.py -q`

Expected: PASS（若 FAIL，说明 jieba 分词粒度异常，检查 `extract_terms` 实现）

- [ ] **Step 3: 提交**

```bash
git add tests/test_match_workflow.py
git commit -m "test: 规则层中文关键词重叠率非零"
```

### Task 3: 市场洞察统计中文技能词

**Files:**
- Modify: `app/services/insight_service.py`
- Test: `tests/test_insight_service.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_insight_service.py` 末尾追加：

```python
def test_insight_chinese_skill_and_stopwords(db_session):
    jd = JD(
        company="京东",
        title="A",
        raw_text="a",
        structured_json={
            "requirements": ["熟悉机器学习与深度学习", "具备良好的沟通能力"],
            "location": "北京",
            "salary": "20-40K·14薪",
        },
    )
    db_session.add(jd)
    db_session.commit()
    report = generate_market_insight(db_session)
    skills = [s["skill"] for s in report["top_skills"]]
    assert "机器学习" in skills
    assert "深度学习" in skills
    assert "熟悉" not in skills
    assert "具备" not in skills
    assert "良好" not in skills
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_insight_service.py::test_insight_chinese_skill_and_stopwords -q`

Expected: FAIL（`"机器学习" not in [...]`）

- [ ] **Step 3: 实现**

在 `app/services/insight_service.py` 中：

1. 扩展 `INSIGHT_STOPWORDS`，追加中文停用词：

```python
INSIGHT_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have", "has", "you", "your",
    "will", "can", "job", "work", "year", "years", "experience", "skill", "skills",
    "good", "strong", "ability", "etc", "e.g", "bad", "case", "use", "used", "using",
    "able", "related", "familiar", "knowledge", "excellent", "team", "design", "development",
    "preferred", "plus", "including", "such", "also",
    # 中文停用词（双字虚词/常见套话）
    "熟悉", "要求", "优先", "经验", "相关", "能够", "具备", "负责", "参与", "了解",
    "掌握", "良好", "能力", "岗位", "工作", "项目", "开发", "设计", "团队", "以及",
    "具有", "进行", "通过", "支持", "使用", "包括", "需要", "我们", "简历", "加分",
    "沟通", "较强", "扎实", "优秀", "严谨", "积极", "主动", "认真", "负责", "善于",
}
```

2. 在 `generate_market_insight` 的过滤条件中增加"以数字开头"的排除（防 `2022届` 这类分词残留）：

```python
                for term in extract_terms(item):
                    if (
                        len(term) >= 2
                        and re.fullmatch(r"\d+([-+/]\d+)*", term) is None
                        and not re.match(r"^\d", term)
                        and term.lower() not in INSIGHT_STOPWORDS
                    ):
                        skills[term] += 1
```

3. `test_insight_stopwords_filtered` 中原有的 `assert "2022" not in skills` 现在由 `not re.match(r"^\d", term)` 兜底，无需改测试。

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_insight_service.py -q`

Expected: PASS（全部，含原有 4 个用例）

- [ ] **Step 5: 提交**

```bash
git add app/services/insight_service.py tests/test_insight_service.py
git commit -m "feat: 市场洞察支持中文技能词并过滤中文停用词"
```

### Task 4: 用 SQLite+BM25+jieba 重写检索层，移除 ChromaDB

**Files:**
- Rewrite: `app/vector_store.py`
- Modify: `app/config.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_vector_store.py`
- Modify: `pyproject.toml`、`requirements.txt`（移除 chromadb）

- [ ] **Step 1: 写失败测试（先锁定新行为）**

在 `tests/test_vector_store.py` 中追加：

```python
def test_query_chinese_doc(vector_store):
    vector_store.add(
        COLLECTION_RESUMES,
        ["熟悉机器学习与 RAG 检索", "熟悉 Java 与 Spring"],
        ["r1", "r2"],
        [{"resume_id": "r1"}, {"resume_id": "r2"}],
    )
    results = vector_store.query(COLLECTION_RESUMES, ["机器学习"], top_k=1)
    assert results[0]["id"] == "r1"
    assert results[0]["text"] == "熟悉机器学习与 RAG 检索"


def test_delete_removes_doc(vector_store):
    vector_store.add(COLLECTION_RESUMES, ["Python"], ["r1"], [{"resume_id": "r1"}])
    vector_store.delete(COLLECTION_RESUMES, ["r1"])
    assert vector_store.query(COLLECTION_RESUMES, ["Python"], top_k=5) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_vector_store.py -q`

Expected: FAIL（`AttributeError: 'VectorStore' object has no attribute 'delete'` 或 ChromaDB 哈希嵌入对中文返回空）

- [ ] **Step 3: 实现新 `app/vector_store.py`**

整体替换为：

```python
import json
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jieba

from app.config import settings

COLLECTION_RESUMES = "resumes"
COLLECTION_JDS = "jds"

_ASCII_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#._-]{1,}")
_HAS_TEXT_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(t.lower() for t in _ASCII_RE.findall(text))
    for word in jieba.cut(text):
        word = word.strip().lower()
        if len(word) >= 2 and _HAS_TEXT_RE.search(word):
            tokens.append(word)
    return tokens


class VectorStore:
    """轻量中文检索：jieba 分词 + BM25 打分，SQLite 持久化文档。

    接口与旧 ChromaDB 版本保持兼容（add/query/delete），调用方无需改动。
    """

    def __init__(self, path: str | None = None):
        self._db_path = Path(path or settings.search_db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS search_docs ("
            " collection TEXT NOT NULL,"
            " doc_id TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " metadata_json TEXT NOT NULL DEFAULT '{}',"
            " updated_at TEXT NOT NULL,"
            " PRIMARY KEY (collection, doc_id)"
            ")"
        )
        self._conn.commit()
        self._documents: dict[str, list[dict[str, Any]]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        rows = self._conn.execute(
            "SELECT collection, doc_id, content, metadata_json FROM search_docs"
        ).fetchall()
        for collection, doc_id, content, metadata_json in rows:
            self._documents.setdefault(collection, []).append(
                {"id": doc_id, "text": content, "metadata": json.loads(metadata_json)}
            )
        self._loaded = True

    def add(
        self,
        collection: str,
        docs: list[str],
        ids: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        self._ensure_loaded()
        now = datetime.now(timezone.utc).isoformat()
        metas = metadatas or [{}] * len(docs)
        for doc, doc_id, meta in zip(docs, ids, metas):
            self._conn.execute(
                "INSERT INTO search_docs "
                "(collection, doc_id, content, metadata_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(collection, doc_id) DO UPDATE SET "
                " content=excluded.content, metadata_json=excluded.metadata_json,"
                " updated_at=excluded.updated_at",
                (collection, doc_id, doc, json.dumps(meta, ensure_ascii=False), now),
            )
            bucket = self._documents.setdefault(collection, [])
            entry = {"id": doc_id, "text": doc, "metadata": meta}
            for i, existing in enumerate(bucket):
                if existing["id"] == doc_id:
                    bucket[i] = entry
                    break
            else:
                bucket.append(entry)
        self._conn.commit()

    def delete(self, collection: str, ids: list[str]) -> None:
        self._ensure_loaded()
        removed = set(ids)
        self._documents[collection] = [
            d for d in self._documents.get(collection, []) if d["id"] not in removed
        ]
        for doc_id in ids:
            self._conn.execute(
                "DELETE FROM search_docs WHERE collection = ? AND doc_id = ?",
                (collection, doc_id),
            )
        self._conn.commit()

    def query(self, collection: str, query_texts: list[str], top_k: int = 5) -> list[dict]:
        self._ensure_loaded()
        docs = self._documents.get(collection, [])
        if not docs:
            return []
        query_tokens = _tokenize(query_texts[0])
        if not query_tokens:
            return []
        doc_tokens = [_tokenize(d["text"]) for d in docs]
        avg_len = sum(len(t) for t in doc_tokens) / len(doc_tokens)
        df = Counter(tok for tokens in doc_tokens for tok in set(tokens))
        n = len(docs)
        scored: list[tuple[float, dict[str, Any]]] = []
        for doc, tokens in zip(docs, doc_tokens):
            freq = Counter(tokens)
            dl = len(tokens)
            score = 0.0
            for qt in query_tokens:
                tf = freq.get(qt, 0)
                if tf == 0:
                    continue
                idf = math.log(1 + (n - df[qt] + 0.5) / (df[qt] + 0.5))
                score += idf * (tf * 2.5) / (tf + 1.5 * (1 - 0.75 + 0.75 * dl / avg_len))
            scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for score, doc in scored[:top_k] if score > 0]
```

将 `app/config.py` 的 `chroma_path: str = "./data/chroma"` 替换为：

```python
    search_db_path: str = "./data/search.db"
```

更新 `tests/conftest.py`：删除 `import chromadb` 和 `DummyEmbeddingFunction` 类，`vector_store` fixture 改为：

```python
@pytest.fixture
def vector_store(tmp_path):
    from app.vector_store import VectorStore

    return VectorStore(path=str(tmp_path / "search.db"))
```

更新 `pyproject.toml` / `requirements.txt`：删除 `chromadb>=0.5.0`。

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_vector_store.py tests/test_jd_service.py tests/test_resume_service.py tests/test_eval_runner.py -q`

Expected: PASS（原有 `test_add_and_query` 现在走 BM25：`"Python LangGraph"` 命中含 `Python` 的文档；`test_create_jd_from_text` 里 `query("jds", ["LLM"])` 命中 `LLM 应用开发实习生`）

- [ ] **Step 5: 提交**

```bash
git add app/vector_store.py app/config.py tests/conftest.py tests/test_vector_store.py pyproject.toml requirements.txt
git commit -m "refactor: ChromaDB 替换为 jieba+BM25+SQLite 轻量检索"
```

### Task 5: JD 列表支持关键词检索（接通只写不读的检索层）

**Files:**
- Modify: `app/main.py`
- Modify: `app/web/src/api.js`、`app/web/src/components/JDPanel.jsx`（前端可选，本次先加 API）
- Test: `tests/test_api.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_api.py` 末尾追加：

```python
def test_list_jds_filter_by_keyword(client, db_session):
    import json

    import app.main as main_module
    from app.models import JD
    from app.vector_store import COLLECTION_JDS

    jd1 = JD(
        company="京东",
        title="机器学习实习生",
        raw_text="a",
        structured_json={"requirements": ["熟悉机器学习"]},
    )
    jd2 = JD(
        company="字节",
        title="前端开发工程师",
        raw_text="b",
        structured_json={"requirements": ["熟悉前端工程化"]},
    )
    db_session.add_all([jd1, jd2])
    db_session.commit()
    main_module.vector_store.add(
        COLLECTION_JDS,
        [json.dumps(jd1.structured_json, ensure_ascii=False), json.dumps(jd2.structured_json, ensure_ascii=False)],
        [jd1.id, jd2.id],
        [{"jd_id": jd1.id}, {"jd_id": jd2.id}],
    )
    res = client.get("/api/jds?q=机器学习")
    assert res.status_code == 200
    titles = [jd["title"] for jd in res.json()["jds"]]
    assert "机器学习实习生" in titles
    assert "前端开发工程师" not in titles
```

注意：不直接走 `POST /api/jds` 是因为 conftest 的 FakeLLM 对任何输入返回同一份 `JD_DATA`，两条 JD 的结构化内容相同、无法区分；改为直接插入不同内容的 JD 并手动写入测试索引。

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_list_jds_filter_by_keyword -q`

Expected: FAIL（返回全部 2 条 JD）

- [ ] **Step 3: 实现**

修改 `app/main.py` 的 `list_jds`：

```python
@app.get("/api/jds")
def list_jds(q: str = "", db: Session = Depends(get_session)):
    from app.models import JD

    query = db.query(JD)
    if q.strip():
        hits = vector_store.query(COLLECTION_JDS, [q.strip()], top_k=20)
        ids = [h["id"] for h in hits]
        if not ids:
            return {"jds": []}
        query = query.filter(JD.id.in_(ids))
    jds = query.order_by(JD.created_at.desc()).limit(50).all()
    return {
        "jds": [
            {
                "jd_id": jd.id,
                "company": jd.company,
                "title": jd.title,
                "display_name": jd_display_name(jd),
                "source_type": jd.source_type,
            }
            for jd in jds
        ]
    }
```

并在 `app/main.py` 顶部 import 中补充 `from app.vector_store import COLLECTION_JDS, VectorStore`（替换现有的 `from app.vector_store import VectorStore`）。

前端加一个可选的最小调用（`app/web/src/api.js`）：

```javascript
export async function listJDs(q = '') {
  const res = await fetch(`/api/jds${q ? `?q=${encodeURIComponent(q)}` : ''}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
```

`JDPanel.jsx` 中的列表加载改为调用 `listJDs(searchTerm)`（搜索框已存在则绑定，不存在则本期只改 API，UI 不强制）。

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q`

Expected: PASS（91+1 个用例，原有 `test_create_jd_text` 等不受影响）

- [ ] **Step 5: 提交**

```bash
git add app/main.py app/web/src/api.js app/web/src/components/JDPanel.jsx tests/test_api.py
git commit -m "feat: JD 列表支持关键词检索"
```

### Task 6: 清理 ChromaDB 残留引用与数据

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/demo-script.md`、`docs/RESUME_BULLETS.md`、`docs/INTERVIEW_PREP.md`（出现 ChromaDB 的字样改为"本地全文检索（jieba+BM25）"）
- Delete: `data/chroma/`（本地旧索引）

- [ ] **Step 1: 改配置与文档**

`.env.example`：把 `CHROMA_PATH=./data/chroma` 改为 `SEARCH_DB_PATH=./data/search.db`。

`README.md`：
- 架构图里 `T --> V[(ChromaDB)]` 改为 `T --> V[(SQLite 全文检索)]`；
- 环境变量表：`CHROMA_PATH` 行改为 `SEARCH_DB_PATH`，说明改为"检索索引路径（SQLite）"；
- 修复断链：`docs/superpowers/specs/2026-08-04-job-copilot-design.md` 不存在，改为指向 `docs/audit-report-2026-08.md`；
- 技术栈一句话里 "ChromaDB" 改为 "jieba+BM25 本地检索"。

`docs/demo-script.md` 与 `docs/RESUME_BULLETS.md` 中出现的 ChromaDB 描述同步替换。

- [ ] **Step 2: 删除旧 ChromaDB 数据（执行前确认路径）**

先确认：

```powershell
Get-ChildItem data\chroma -ErrorAction SilentlyContinue
```

确认该目录仅包含 Chroma 遗留文件后删除（启动新索引后会自动重建 `data/search.db`）：

```powershell
Remove-Item -Recurse -Force data\chroma
```

- [ ] **Step 3: 全量回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -q`

Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add .env.example README.md docs/ app/
git commit -m "docs: 清理 ChromaDB 引用并修复 README 断链"
```

---

## 阶段 2：后台任务与 SSE 改为数据库持久化（报告 P0-3）

### Task 7: 新增 MatchTask 模型与事件追加助手

**Files:**
- Modify: `app/models.py`
- Modify: `app/main.py`（`run_matches_task` 重写、`create_match` 建任务行）
- Test: `tests/test_api.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_api.py` 追加：

```python
from app.models import MatchTask


def test_create_match_persists_task_row(client, db_session, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "run_matches_task", lambda *a, **k: None)
    res = client.post("/api/matches", json={"resume_id": "r1", "jd_ids": ["j1"]})
    assert res.status_code == 200
    task = db_session.get(MatchTask, res.json()["task_id"])
    assert task is not None
    assert task.status == "running"
    assert task.jd_ids_json == ["j1"]


def test_sse_replays_persisted_events(client, db_session):
    task = MatchTask(
        id="t-replay",
        resume_id="r1",
        jd_ids_json=["j1"],
        status="completed",
        events_json=[
            {"type": "started", "total": 1, "seq": 1},
            {"type": "match_result", "result": {"match_id": "m1"}, "seq": 2},
            {"type": "completed", "seq": 3},
        ],
    )
    db_session.add(task)
    db_session.commit()
    with client.stream("GET", "/api/matches/t-replay/stream") as response:
        body = b"".join(response.iter_bytes()).decode()
    assert "started" in body
    assert "match_result" in body
    assert "completed" in body


def test_sse_missing_task_404(client):
    res = client.get("/api/matches/nope/stream")
    assert res.status_code == 404


def test_recover_interrupted_tasks(db_session):
    from app.main import recover_interrupted_tasks

    task = MatchTask(id="t-stale", resume_id="r", jd_ids_json=[], status="running", events_json=[])
    db_session.add(task)
    db_session.commit()
    recover_interrupted_tasks(db_session)
    recovered = db_session.get(MatchTask, "t-stale")
    assert recovered.status == "error"
    assert "服务重启" in recovered.error
```

并把原 `test_sse_stream_delivers_completed_event` 删除（它依赖将被移除的 `event_bus`），同时把 `tests/test_api.py` 顶部的 `import threading`、`import time`、`from app.events import event_bus` 删除（`import fitz` 保留，`test_upload_then_confirm_flow` 仍用）。

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q`

Expected: FAIL（`MatchTask` 表不存在 / `run_matches_task` 未持久化 / stream 走旧逻辑）

- [ ] **Step 3: 实现**

`app/models.py` 末尾追加：

```python
class MatchTask(Base):
    __tablename__ = "match_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_id: Mapped[str] = mapped_column(String(32), default="")
    jd_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="running")
    events_json: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
```

`app/main.py`：

1. 删除 `import queue as queue_module`、`from app.events import event_bus`、`import threading` 保留（后台线程仍用）。
2. 在 `app.main` 顶部 import 增加 `from app.models import MatchTask`。
3. 把 `run_matches_task` 整体替换为：

```python
def _now_utc():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _append_task_event(db: Session, task_id: str, event: dict) -> None:
    task = db.get(MatchTask, task_id)
    if task is None:
        return
    events = list(task.events_json)
    event = {**event, "seq": len(events) + 1}
    events.append(event)
    task.events_json = events
    task.updated_at = _now_utc()
    db.commit()


def run_matches_task(
    task_id: str,
    resume_id: str,
    jd_ids: list[str],
    session_factory=SessionLocal,
) -> None:
    db = session_factory()
    try:
        _append_task_event(db, task_id, {"type": "started", "total": len(jd_ids)})
        for index, jd_id in enumerate(jd_ids):
            _append_task_event(
                db,
                task_id,
                {"type": "match_progress", "index": index, "total": len(jd_ids), "jd_id": jd_id},
            )
            result = match_service.run_match(db, resume_id, jd_id, vector_store, llm=llm)
            _append_task_event(db, task_id, {"type": "match_result", "result": result.model_dump()})
        _append_task_event(db, task_id, {"type": "completed"})
    except Exception as exc:
        _append_task_event(db, task_id, {"type": "error", "message": str(exc)})
        task = db.get(MatchTask, task_id)
        if task is not None:
            task.status = "error"
            task.error = str(exc)
            task.updated_at = _now_utc()
            db.commit()
    finally:
        db.close()
```

4. `create_match` 替换为：

```python
@app.post("/api/matches")
def create_match(payload: MatchRequest, db: Session = Depends(get_session)):
    task_id = uuid.uuid4().hex
    task = MatchTask(
        id=task_id,
        resume_id=payload.resume_id,
        jd_ids_json=payload.jd_ids,
        status="running",
        events_json=[],
    )
    db.add(task)
    db.commit()
    threading.Thread(
        target=run_matches_task,
        args=(task_id, payload.resume_id, payload.jd_ids),
        daemon=True,
    ).start()
    return {"task_id": task_id}
```

5. `match_stream` 替换为（删除事件总线订阅）：

```python
@app.get("/api/matches/{task_id}/stream")
async def match_stream(task_id: str, db: Session = Depends(get_session)):
    task = db.get(MatchTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    async def gen():
        cursor = 0
        while True:
            task = db.get(MatchTask, task_id)
            if task is None:
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"type": "error", "message": "task not found"}, ensure_ascii=False
                    ),
                }
                return
            new_events = [e for e in task.events_json if e.get("seq", 0) > cursor]
            for event in new_events:
                cursor = event["seq"]
                yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
                if event["type"] in ("completed", "error"):
                    return
            await asyncio.sleep(0.5)

    return EventSourceResponse(gen())
```

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q`

Expected: 全部 PASS（`tests/test_events.py` 将在 Task 8 删除）

- [ ] **Step 5: 提交**

```bash
git add app/models.py app/main.py tests/test_api.py
git commit -m "feat: 匹配任务改为数据库持久化，SSE 从任务表回放事件"
```

### Task 8: 删除事件总线并加启动恢复

**Files:**
- Delete: `app/events.py`、`tests/test_events.py`
- Modify: `app/main.py`（lifespan 启动恢复中断任务）

- [ ] **Step 1: 删除事件总线**

删除 `app/events.py` 与 `tests/test_events.py`，并把 `app/main.py` 中所有 `event_bus` 引用清理干净（Task 7 已完成引用移除）。

全项目搜索确认无残留：

```bash
rg -n "event_bus|app.events"
```

Expected: 无输出

- [ ] **Step 2: 实现 lifespan 与恢复函数**

`app/main.py`：

1. 顶部 import 改为：

```python
from contextlib import asynccontextmanager
```

2. 新增可单测的恢复函数（放在 `create_match` 之前）：

```python
def recover_interrupted_tasks(db: Session) -> int:
    count = (
        db.query(MatchTask)
        .filter(MatchTask.status == "running")
        .update({"status": "error", "error": "服务重启，任务中断"})
    )
    db.commit()
    return count
```

3. 删除 `@app.on_event("startup")` 块，替换为：

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.db import Base, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        recover_interrupted_tasks(db)
    finally:
        db.close()
    yield
```

4. `app = FastAPI(title=settings.app_name, lifespan=lifespan)`。

- [ ] **Step 3: 运行确认**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -q`

Expected: PASS 且无 DeprecationWarning（`on_event` 已移除）

- [ ] **Step 5: 提交**

```bash
git add app/events.py app/main.py tests/test_events.py tests/test_api.py
git commit -m "refactor: 移除进程内事件总线，lifespan 恢复中断任务"
```

---

## 阶段 3：数据一致性与删除清理（报告 P0-4、P1-16）

### Task 9: 启用 SQLite 外键并级联清理

**Files:**
- Modify: `app/db.py`
- Modify: `app/main.py`（`delete_jds_batch`）
- Modify: `app/vector_store.py`（`delete` 已在 Task 4 实现）
- Test: `tests/test_api.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_api.py` 追加：

```python
from app.models import Application, JD, Match


def test_batch_delete_jd_cascades(client, db_session):
    resume = Resume(raw_text="r", structured_json={}, status="confirmed")
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=80.0)
    db_session.add(match)
    db_session.commit()
    app_row = Application(match_id=match.id, current_status="applied", status_history_json=[])
    db_session.add(app_row)
    db_session.commit()

    res = client.post("/api/jds/batch-delete", json={"jd_ids": [jd.id]})
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    assert db_session.get(Match, match.id) is None
    assert db_session.get(Application, app_row.id) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_batch_delete_jd_cascades -q`

Expected: FAIL（`db_session.get(Match, ...)` 仍存在）

- [ ] **Step 3: 实现**

`app/db.py` 顶部加：

```python
from sqlalchemy import create_engine, event
```

在 `engine = create_engine(...)` 之后追加：

```python
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

`app/main.py` 的 `delete_jds_batch` 替换为：

```python
@app.post("/api/jds/batch-delete")
def delete_jds_batch(payload: dict, db: Session = Depends(get_session)):
    from app.models import Application, InterviewSession, JD, JDReport, Match

    jd_ids = payload.get("jd_ids", [])
    if not isinstance(jd_ids, list) or not jd_ids:
        raise HTTPException(status_code=400, detail="jd_ids 必填且为非空数组")
    match_ids = [m.id for m in db.query(Match).filter(Match.jd_id.in_(jd_ids)).all()]
    if match_ids:
        db.query(Application).filter(Application.match_id.in_(match_ids)).delete(
            synchronize_session=False
        )
    db.query(InterviewSession).filter(InterviewSession.jd_id.in_(jd_ids)).delete(
        synchronize_session=False
    )
    if match_ids:
        db.query(Match).filter(Match.id.in_(match_ids)).delete(synchronize_session=False)
    db.query(JDReport).filter(JDReport.jd_id.in_(jd_ids)).delete(synchronize_session=False)
    deleted = db.query(JD).filter(JD.id.in_(jd_ids)).delete(synchronize_session=False)
    db.commit()
    vector_store.delete(COLLECTION_JDS, jd_ids)
    return {"deleted": deleted}
```

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/db.py app/main.py tests/test_api.py
git commit -m "fix: 批量删 JD 级联清理投递/匹配/面试与索引"
```

### Task 10: 同一岗位防重复投递 + 上传失败清理孤儿文件

**Files:**
- Modify: `app/models.py`、`app/services/application_service.py`
- Modify: `app/main.py`（上传）
- Test: `tests/test_application_service.py`、`tests/test_api.py`

- [ ] **Step 1: 写失败测试**

`tests/test_application_service.py` 追加：

```python
from sqlalchemy.exc import IntegrityError


def test_duplicate_application_raises(db_session):
    match_id = _make_match(db_session)
    create_application(db_session, match_id)
    with pytest.raises((IntegrityError, ValueError)):
        create_application(db_session, match_id)
```

`tests/test_api.py` 追加：

```python
def test_upload_failure_cleans_orphan_file(client, db_session, monkeypatch, tmp_path):
    from app import main as main_module

    def boom(*a, **k):
        raise RuntimeError("parse failed")

    monkeypatch.setattr(main_module.resume_service, "create_resume_from_file", boom)
    pdf_path = tmp_path / "bad.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 fake")
    with open(pdf_path, "rb") as f:
        res = client.post("/api/resume/upload", files={"file": ("bad.pdf", f, "application/pdf")})
    assert res.status_code == 422
    upload_dir = main_module.Path(main_module.settings.upload_dir)
    assert list(upload_dir.glob("*.pdf")) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_application_service.py tests/test_api.py -q`

Expected: 两个新测试 FAIL

- [ ] **Step 3: 实现**

`app/models.py` 的 `Application` 类加唯一约束：

```python
class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("match_id", name="uq_application_match_id"),)
```

并在文件顶部 import 增加 `UniqueConstraint`（从 `sqlalchemy`）。

`app/services/application_service.py` 的 `create_application` 改为：

```python
from sqlalchemy.exc import IntegrityError


def create_application(db: Session, match_id: str, notes: str = "") -> Application:
    match = db.get(Match, match_id)
    if match is None:
        raise KeyError(f"match not found: {match_id}")
    application = Application(
        match_id=match_id,
        current_status="applied",
        status_history_json=[{"status": "applied", "at": _now().isoformat()}],
        notes=notes,
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("该岗位已创建投递记录") from None
    db.refresh(application)
    return application
```

`app/main.py` 的 `upload_resume` 改为：

```python
@app.post("/api/resume/upload")
def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_session)):
    suffix = Path(file.filename or "resume.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    try:
        file_path.write_bytes(file.file.read())
        resume = resume_service.create_resume_from_file(db, str(file_path), vector_store, llm=llm)
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"简历解析失败: {exc}") from exc
    return {
        "resume_id": resume.id,
        "status": resume.status,
        "structured": resume.structured_json,
    }
```

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_application_service.py tests/test_api.py -q`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/models.py app/services/application_service.py app/main.py tests/test_application_service.py tests/test_api.py
git commit -m "fix: 投递记录唯一约束，上传失败清理孤儿文件"
```

---

## 阶段 4：LLM 层工程化（报告 P1-6、P1-7 部分）

### Task 11: LLMService 超时、退避重试、JSON 模式与日志

**Files:**
- Modify: `app/config.py`、`app/llm.py`
- Modify: `pyproject.toml`、`requirements.txt`（无新增依赖，仅配置）
- Test: `tests/test_llm.py`

- [ ] **Step 1: 写失败测试**

`tests/test_llm.py` 追加：

```python
class _RaisingClient:
    def __init__(self, fail_count=1):
        self.fail_count = fail_count
        self.calls = 0
        self.chat = _FakeChat(["ok"])

    def _create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_count:
            exc = RuntimeError("rate limited")
            exc.status_code = 429
            raise exc
        return self.chat.completions.create(**kwargs)


class FakeRaisingClient:
    def __init__(self):
        self.completions = _RaisingClient()


def test_complete_retries_on_429():
    client = FakeRaisingClient()
    svc = LLMService(client=client, max_retries=2)
    assert svc.complete([{"role": "user", "content": "hi"}]) == "ok"
    assert client.completions.calls == 2


class _JsonModeRejectClient:
    def __init__(self):
        self.chat = _FakeChat(['{"name": "王五"}'])
        self.calls = []

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("response_format"):
            exc = RuntimeError("unsupported")
            exc.status_code = 400
            raise exc
        return self.chat.completions.create(**kwargs)


class FakeJsonRejectClient:
    def __init__(self):
        self.completions = _JsonModeRejectClient()


def test_complete_structured_falls_back_without_json_mode():
    client = FakeJsonRejectClient()
    svc = LLMService(client=client, max_retries=0)
    result = svc.complete_structured([{"role": "user", "content": "x"}], ResumeStructured)
    assert result["name"] == "王五"
    assert client.completions.calls[0].get("response_format") is not None
    assert "response_format" not in client.completions.calls[-1]
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm.py -q`

Expected: 新测试 FAIL

- [ ] **Step 3: 实现**

`app/config.py` 增加：

```python
    llm_timeout: float = 120.0
    llm_max_retries: int = 2
    llm_json_mode: bool = True
```

`app/llm.py` 整体替换为：

```python
import json
import logging
import re
import time
from typing import Any, Type

from openai import OpenAI
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 调用封装：普通补全 + 结构化 JSON 输出，带退避重试与可选 json 模式。"""

    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        json_mode: bool | None = None,
    ):
        self.timeout = timeout if timeout is not None else settings.llm_timeout
        self.max_retries = (
            max_retries if max_retries is not None else settings.llm_max_retries
        )
        self.json_mode = settings.llm_json_mode if json_mode is None else json_mode
        self.client = client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "EMPTY",
            timeout=self.timeout,
        )
        self.model = model or settings.llm_model

    def _log_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        logger.info(
            "llm_complete model=%s prompt_tokens=%s completion_tokens=%s",
            self.model,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
        )

    def complete(self, messages: list[dict[str, str]], max_tokens: int = 2000, **kwargs) -> str:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                self._log_usage(response)
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_exc = exc
                status = getattr(exc, "status_code", None)
                retryable = status is None or status >= 500 or status == 429
                if attempt < self.max_retries and retryable:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise
        raise last_exc  # type: ignore[misc]

    def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[BaseModel],
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """要求模型输出符合 schema 的 JSON；解析失败带错误重试一次。"""
        instruction = (
            "You must respond with a single JSON object matching this schema exactly:\n"
            f"{schema.model_json_schema()}\n"
            "No markdown fences. No commentary."
        )
        for attempt in range(2):
            try:
                kwargs = {"response_format": {"type": "json_object"}} if self.json_mode else {}
                text = self.complete(
                    messages + [{"role": "system", "content": instruction}],
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except Exception:
                if self.json_mode:
                    self.json_mode = False
                    continue
                raise
            try:
                data = self._extract_json(text)
                return schema.model_validate(data).model_dump()
            except Exception as exc:
                if attempt == 0:
                    messages = messages + [
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

注意：`FakeClient` 等测试桩的 `create(**kwargs)` 均兼容新增 kwargs；`test_complete_structured_parses_fenced_json` 仍通过（json_mode 默认 True 时发送 `response_format`，测试桩忽略即可）。

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm.py tests/test_supervisor.py tests/test_resume_agent.py -q`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/config.py app/llm.py tests/test_llm.py
git commit -m "feat: LLM 层超时/退避重试/json 模式降级/用量日志"
```

---

## 阶段 5：工程化收尾（报告 P1-8、P1-9、P1-10、P1-11、P1-12、P1-14、P1-15）

### Task 12: 匹配图改为模块级缓存

**Files:**
- Modify: `app/workflow/graph.py`
- Test: `tests/test_match_workflow.py`

- [ ] **Step 1: 写测试**

`tests/test_match_workflow.py` 追加：

```python
import app.workflow.graph as graph_module


def test_default_graph_is_cached():
    first = build_match_graph(None)
    assert graph_module._default_graph is not None
    assert build_match_graph(None) is first
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_match_workflow.py::test_default_graph_is_cached -q`

Expected: FAIL（`_default_graph` 未定义）

- [ ] **Step 3: 实现**

`app/workflow/graph.py`：

1. `build_match_graph` 改为：

```python
_default_graph = None


def build_match_graph(llm=None):
    if llm is None:
        global _default_graph
        if _default_graph is None:
            from app.llm import LLMService

            _default_graph = _build(LLMService())
        return _default_graph
    return _build(llm)


def _build(llm):
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
            "必须输出顶层 JSON 字段（不要嵌套 dimensions，不要多余字段），格式：\n"
            '{"skill_match": 0-100, "experience_match": 0-100, "education_match": 0-100, '
            '"hard_requirements": 0-100, "reasons": {"skill_match": "理由"}, '
            '"gaps": ["中文差距建议，最多3条"], "summary": "一句话总结"}\n'
            "评分维度说明：skill_match(技能匹配)/experience_match(经历相关)/"
            "education_match(教育背景)/hard_requirements(硬性条件)，每项 0-100。"
        )
        messages = [{"role": "user", "content": prompt}]
        data = llm.complete_structured(messages, MatchScoring)
        if all(data[k] == 0 for k in WEIGHTS):
            data = llm.complete_structured(
                messages
                + [
                    {
                        "role": "user",
                        "content": (
                            "上一次输出所有评分维度均为 0。请重新评估，并确保输出顶层 "
                            "skill_match/experience_match/education_match/hard_requirements "
                            "四个 0-100 数值字段（不要嵌套、不要省略）。"
                        ),
                    }
                ],
                MatchScoring,
            )
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

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_match_workflow.py tests/test_match_service.py -q`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/workflow/graph.py tests/test_match_workflow.py
git commit -m "perf: 匹配图按默认 LLM 缓存，避免每次编译"
```

### Task 13: 消除列表接口 N+1 查询

**Files:**
- Modify: `app/main.py`（`list_interviews`）
- Modify: `app/services/application_service.py`（`list_applications`、`get_reminders`）
- Test: `tests/test_api_phase3.py`、`tests/test_application_service.py`

- [ ] **Step 1: 写断言测试（证明行为不变且查询次数受限）**

`tests/test_application_service.py` 追加：

```python
def test_list_applications_single_jd_lookup(db_session):
    from sqlalchemy import event as sa_event

    match_id = _make_match(db_session)
    create_application(db_session, match_id)
    counts = []

    @sa_event.listens_for(db_session, "after_cursor_execute")
    def _count(_conn, _cursor, _stmt, _params, _context, _executemany):
        counts.append(1)

    list_applications(db_session)
    assert len(counts) <= 3  # 1 次查应用 + 1 次 join 出 JD 名，不允许逐条查询
```

- [ ] **Step 2: 运行确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_application_service.py::test_list_applications_single_jd_lookup -q`

Expected: FAIL（当前逐条 `_resolve_jd_name` 触发多次查询）

- [ ] **Step 3: 实现**

`app/services/application_service.py` 新增：

```python
def _jd_names_by_match(db: Session, match_ids: list[str]) -> dict[str, str]:
    if not match_ids:
        return {}
    rows = (
        db.query(Match.id, JD.id)
        .join(JD, JD.id == Match.jd_id)
        .filter(Match.id.in_(match_ids))
        .all()
    )
    jd_ids = list({jd_id for _, jd_id in rows})
    jds = {}
    if jd_ids:
        jds = {jd.id: jd for jd in db.query(JD).filter(JD.id.in_(jd_ids)).all()}
    return {
        match_id: jd_display_name(jds[jd_id]) if jd_id in jds else ""
        for match_id, jd_id in rows
    }
```

`list_applications` 与 `get_reminders` 改为：

```python
def list_applications(db: Session) -> list[dict]:
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    names = _jd_names_by_match(db, [a.match_id for a in apps])
    return [to_payload(a, names.get(a.match_id, "")) for a in apps]


def get_reminders(db: Session) -> list[dict]:
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    names = _jd_names_by_match(db, [a.match_id for a in apps])
    reminders = []
    for a in apps:
        if a.reminder_at and a.reminder_at <= _now():
            reminders.append(to_payload(a, names.get(a.match_id, "")))
        elif follow_up_suggestion(a):
            reminders.append(to_payload(a, names.get(a.match_id, "")))
    return reminders
```

`app/main.py` 的 `list_interviews` 改为一次 join 取 JD 名：

```python
@app.get("/api/interviews/sessions")
def list_interviews(db: Session = Depends(get_session)):
    from app.models import JD

    rows = (
        db.query(InterviewSession, JD)
        .outerjoin(JD, JD.id == InterviewSession.jd_id)
        .order_by(InterviewSession.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "sessions": [
            {
                "session_id": s.id,
                "jd_id": s.jd_id,
                "jd_name": jd_display_name(jd) if jd else "",
                "resume_id": s.resume_id,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "overall_score": (s.summary_json or {}).get("overall_score", 0),
            }
            for s, jd in rows
        ]
    }
```

- [ ] **Step 4: 运行确认通过**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_application_service.py tests/test_api_phase3.py -q`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/main.py app/services/application_service.py tests/test_application_service.py
git commit -m "perf: 列表接口消除 N+1 查询"
```

### Task 14: 引入 Alembic 迁移

**Files:**
- Create: `alembic.ini`、`migrations/env.py`、`migrations/script.py.mako`、`migrations/versions/0001_initial.py`
- Modify: `pyproject.toml`、`requirements.txt`（加 alembic）
- Modify: `README.md`（迁移说明）

- [ ] **Step 1: 安装并初始化**

```bash
.\.venv\Scripts\python.exe -m pip install "alembic>=1.13.0"
.\.venv\Scripts\python.exe -m alembic init migrations
```

在 `pyproject.toml` dependencies 与 `requirements.txt` 中加 `alembic>=1.13.0`。

- [ ] **Step 2: 配置 env.py 指向项目数据库**

把 `migrations/env.py` 中 `config.set_main_option("sqlalchemy.url", ...)` 段替换为：

```python
from app.config import settings
from app.db import Base
from app import models  # noqa: F401  确保所有模型被导入

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

并把 `alembic.ini` 中的 `sqlalchemy.url` 行注释掉（由 env.py 注入）。

- [ ] **Step 3: 生成初始迁移并升级**

```bash
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "initial schema"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Expected: `Running upgrade ... -> 0001, initial schema`，随后在 `data/job_copilot.db` 生成 `alembic_version` 表。

注意：本机已有数据库时 autogenerate 可能检测到与旧表差异（如新增 `match_tasks`），手工检查生成的 `0001_initial.py`，确保它是"完整建表"版本（迁移面向全新库）。

- [ ] **Step 4: 验证全新库可迁移**

```powershell
$env:DATABASE_URL="sqlite:///./data/migrate_test.db"
.\.venv\Scripts\python.exe -m alembic upgrade head
Remove-Item data\migrate_test.db
```

Expected: 无错误；`data/migrate_test.db` 被清理。

- [ ] **Step 5: 提交**

```bash
git add alembic.ini migrations pyproject.toml requirements.txt README.md
git commit -m "chore: 引入 Alembic 数据库迁移"
```

### Task 15: 锁定依赖版本

**Files:**
- Modify: `requirements.txt`（由 pip-tools 生成）
- Create: `requirements-dev.txt`

- [ ] **Step 1: 安装 pip-tools 并编译**

```bash
.\.venv\Scripts\python.exe -m pip install pip-tools
.\.venv\Scripts\python.exe -m piptools compile pyproject.toml --output-file requirements.txt --strip-extras
.\.venv\Scripts\python.exe -m piptools compile pyproject.toml --extra dev --output-file requirements-dev.txt --strip-extras
```

Expected: `requirements.txt` 所有依赖变为 `==` 精确版本（含传递依赖）。

- [ ] **Step 2: 验证全量测试**

Run: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt && .\.venv\Scripts\python.exe -m pytest tests/ -q`

Expected: PASS（若网络受限导致安装失败，改为仅提交编译产物，并在 CI 中验证）

- [ ] **Step 3: 提交**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "chore: 锁定依赖版本"
```

### Task 16: 接入 ruff 并增强 CI

**Files:**
- Modify: `pyproject.toml`、`requirements-dev.txt`
- Modify: `.github/workflows/ci.yml`
- Modify: `app/web/package.json`（无新增，仅确认 build 脚本存在）

- [ ] **Step 1: 加 ruff 配置**

`pyproject.toml` 追加：

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E9", "F"]
```

`requirements-dev.txt` 追加 `ruff==<当前最新版本>`（以 pip 解析结果为准）。

- [ ] **Step 2: 本地跑 ruff 并修复**

```bash
.\.venv\Scripts\python.exe -m pip install ruff
.\.venv\Scripts\python.exe -m ruff check app tests scripts
```

Expected: `All checks passed!`。若有 F 类错误（未使用 import、未定义名），逐个修复后重跑。

- [ ] **Step 3: 更新 CI**

`.github/workflows/ci.yml` 替换为：

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install dependencies
        run: |
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Lint
        run: ruff check app tests scripts
      - name: Migrate
        run: |
          export DATABASE_URL="sqlite:///./ci_test.db"
          alembic upgrade head
      - name: Run tests with coverage
        run: pytest tests/ --cov=app --cov-report=term-missing

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: app/web/package-lock.json
      - name: Install and build
        working-directory: app/web
        run: |
          npm ci
          npm run build
```

- [ ] **Step 4: 提交**

```bash
git add pyproject.toml requirements-dev.txt .github/workflows/ci.yml
git commit -m "ci: 接入 ruff、Alembic 迁移检查与前端构建"
```

### Task 17: golden set 可移植化

**Files:**
- Create: `scripts/seed_eval_data.py`
- Modify: `data/golden_set.json`
- Modify: `README.md`（评测说明）
- Modify: `docs/eval-baseline.md`（注明重新记基线）

- [ ] **Step 1: 写种子脚本（含固定 ID）**

创建 `scripts/seed_eval_data.py`：

```python
"""生成可移植的评测样例数据与 golden set。

用法: python scripts/seed_eval_data.py
用确定性 UUID 保证任何环境跑出相同的 ID，golden_set.json 才能跨环境复用。
"""

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import JD, Match, Resume  # noqa: E402


def fixed_id(key: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"job-copilot-eval/{key}").hex


RESUMES = {
    "resume-backend": {
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
                "tech": ["LangGraph", "FastAPI"],
                "highlights": ["Planner-Researcher-Writer-Reviewer 四 Agent 协作"],
            }
        ],
        "skills": ["Python", "LangGraph", "FastAPI", "RAG", "SQL"],
    },
}

JDS = {
    "jd-llm-dev": {
        "company": "京东",
        "title": "LLM 应用开发实习生",
        "location": "北京",
        "salary": "面议",
        "responsibilities": ["参与 Agent 功能开发", "维护 RAG 检索链路"],
        "requirements": ["熟悉 Python", "了解 LangGraph 或类似编排框架", "有 RAG 项目经验优先"],
    },
    "jd-backend": {
        "company": "腾讯",
        "title": "后端开发实习生",
        "location": "深圳",
        "salary": "20-40K·14薪",
        "responsibilities": ["负责服务端接口开发", "参与系统性能优化"],
        "requirements": ["熟悉 Python/Go", "了解 MySQL 与 Redis", "有高并发项目经验加分"],
    },
}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        resume_ids = {}
        for key, data in RESUMES.items():
            rid = fixed_id(key)
            db.merge(
                Resume(
                    id=rid,
                    source_type="seed",
                    raw_text=json.dumps(data, ensure_ascii=False),
                    structured_json=data,
                    status="confirmed",
                )
            )
            resume_ids[key] = rid
        jd_ids = {}
        for key, data in JDS.items():
            jid = fixed_id(key)
            db.merge(
                JD(
                    id=jid,
                    source_type="seed",
                    company=data["company"],
                    title=data["title"],
                    raw_text=json.dumps(data, ensure_ascii=False),
                    structured_json=data,
                )
            )
            jd_ids[key] = jid
        match = db.merge(
            Match(
                id=fixed_id("match-llm"),
                resume_id=resume_ids["resume-backend"],
                jd_id=jd_ids["jd-llm-dev"],
                total_score=75.0,
            )
        )
        db.commit()
    finally:
        db.close()

    golden = [
        {
            "title": "match-1-后端简历 vs LLM 开发岗",
            "task_type": "match",
            "input": {"resume_id": resume_ids["resume-backend"], "jd_id": jd_ids["jd-llm-dev"]},
            "expected": {"total_min": 40, "total_max": 95},
        },
        {
            "title": "match-2-后端简历 vs 后端岗",
            "task_type": "match",
            "input": {"resume_id": resume_ids["resume-backend"], "jd_id": jd_ids["jd-backend"]},
            "expected": {"total_min": 50, "total_max": 95},
        },
        {
            "title": "cover-letter-llm",
            "task_type": "cover_letter",
            "input": {"match_id": match.id},
            "expected": {"keywords": ["Agent"], "min_score": 0.5},
        },
    ]
    out = ROOT / "data" / "golden_set.json"
    out.write_text(json.dumps(golden, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"seeded {len(RESUMES)} resumes, {len(JDS)} jds, 1 match -> {out}")


if __name__ == "__main__":
    main()
```

注意：旧 golden set 引用的是本机数据库的真实 UUID，无法移植，将被本脚本的样例数据替换；这是刻意取舍。你的真实用例可在跑通后按 `docs/eval-baseline.md` 流程重新追加。

- [ ] **Step 2: 运行脚本并验证**

```bash
.\.venv\Scripts\python.exe scripts/seed_eval_data.py
.\.venv\Scripts\python.exe -m pytest tests/test_eval_golden.py -q
```

Expected: 脚本打印 seeded 信息；`data/golden_set.json` 内为固定 ID；golden 同步测试通过。

手工验证同步：

```bash
.\.venv\Scripts\python.exe -c "from app.db import SessionLocal; from app.eval.golden import sync_golden_set; db=SessionLocal(); print(sync_golden_set(db, 'data/golden_set.json')); db.close()"
```

Expected: `{"added": 3, "updated": 0, "deleted": <旧用例数>, "total": 3}`（首次在旧库上跑会删除旧用例）。

- [ ] **Step 3: 更新文档并提交**

`README.md` 评测章节补充"新环境先运行 `python scripts/seed_eval_data.py` 再同步 golden set"；`docs/eval-baseline.md` 顶部加一行"2026-08-09 golden set 已替换为可移植样例数据，基线需重新记录"。

```bash
git add scripts/seed_eval_data.py data/golden_set.json README.md docs/eval-baseline.md
git commit -m "feat: golden set 可移植化，新增种子脚本"
```

### Task 18: 全量回归与收尾

**Files:**
- Modify: 无（纯验证）

- [ ] **Step 1: 全量测试 + lint + 前端构建**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m ruff check app tests scripts
cd app/web && npm ci && npm run build
```

Expected: 全部 PASS / `All checks passed!` / 构建成功生成 `dist/`

- [ ] **Step 2: 更新基线记录并提交**

把最新 run 的通过率写入 `docs/eval-baseline.md`（若与旧基线不同，注明原因：检索层替换与 golden set 更新）。

```bash
git add docs/eval-baseline.md
git commit -m "docs: 记录审计整改后评测基线"
```

---

## 阶段 6（可选，长期）：任务队列、可观测性与鉴权

> 本阶段依赖部署决策（是否需要 Redis、是否对外发布），适合在阶段 1-5 合并后单独评估。以下为可直接执行的落地步骤。

### Task 19: 迁移到 ARQ 异步任务队列

**Files:**
- Create: `app/worker.py`、`docker-compose.yml`（加 redis 服务）
- Modify: `app/main.py`（`create_match` 改投递 ARQ）
- Modify: `pyproject.toml`、`requirements.txt`（加 arq）

- [ ] **Step 1: 写 worker**

`app/worker.py`：

```python
import asyncio

from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.models import MatchTask
from app.services import match_service
from app.db import SessionLocal
from app.vector_store import VectorStore

vector_store = VectorStore()


def _append_event(db, task_id: str, event: dict) -> None:
    task = db.get(MatchTask, task_id)
    if task is None:
        return
    events = list(task.events_json)
    event = {**event, "seq": len(events) + 1}
    events.append(event)
    task.events_json = events
    db.commit()


async def run_matches_task(ctx, task_id: str, resume_id: str, jd_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        _append_event(db, task_id, {"type": "started", "total": len(jd_ids)})
        for jd_id in jd_ids:
            _append_event(
                db,
                task_id,
                {"type": "match_progress", "index": jd_ids.index(jd_id), "total": len(jd_ids), "jd_id": jd_id},
            )
            result = match_service.run_match(db, resume_id, jd_id, vector_store)
            _append_event(db, task_id, {"type": "match_result", "result": result.model_dump()})
        _append_event(db, task_id, {"type": "completed"})
    except Exception as exc:
        _append_event(db, task_id, {"type": "error", "message": str(exc)})
        task = db.get(MatchTask, task_id)
        if task is not None:
            task.status = "error"
            task.error = str(exc)
            db.commit()
    finally:
        db.close()


async def startup(ctx):
    ctx["redis"] = await create_pool(RedisSettings.from_dsn(settings.redis_dsn))


class WorkerSettings:
    functions = [run_matches_task]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_dsn)
```

`app/config.py` 加 `redis_dsn: str = "redis://localhost:6379/0"`。

- [ ] **Step 2: 改投递与 compose**

`app/main.py` 的 `create_match` 改为 `await` 投递（改 async 函数）：

```python
@app.post("/api/matches")
async def create_match(payload: MatchRequest, db: Session = Depends(get_session)):
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.config import settings as _settings
    from app.models import MatchTask

    task_id = uuid.uuid4().hex
    db.add(MatchTask(id=task_id, resume_id=payload.resume_id, jd_ids_json=payload.jd_ids))
    db.commit()
    redis = await create_pool(RedisSettings.from_dsn(_settings.redis_dsn))
    await redis.enqueue_job("run_matches_task", task_id, payload.resume_id, payload.jd_ids)
    await redis.aclose()
    return {"task_id": task_id}
```

SSE 端不变（阶段 2 已改为读任务表）。

`docker-compose.yml` 增加：

```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "${REDIS_PORT:-6379}:6379"
```

- [ ] **Step 3: 验证**

Run: `.\.venv\Scripts\python.exe -m arq app.worker.WorkerSettings`（需本地 Redis）

Expected: worker 启动，投递后任务事件写入 `match_tasks`，SSE 正常输出。

- [ ] **Step 4: 提交**

```bash
git add app/worker.py app/config.py app/main.py docker-compose.yml pyproject.toml requirements.txt
git commit -m "feat: 匹配任务迁移 ARQ 队列"
```

### Task 20（可选）: 接入 Langfuse 可观测性

- [ ] **Step 1:** 安装 `langfuse`，在 `app/llm.py` 的 `_log_usage` 中改为同时上报 trace（`langfuse.observe()` 装饰或手动 `trace.generation(...)`），配置 `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST` 环境变量。
- [ ] **Step 2:** 本地起 Langfuse（`docker compose up langfuse`，官方 compose 文件）验证一次匹配流程出现完整 trace。
- [ ] **Step 3:** 提交并记录在 `docs/audit-report-2026-08.md` 的"已落地"清单。

### Task 21（可选）: 简单鉴权

- [ ] **Step 1:** `app/config.py` 加 `api_token: str = ""`；`app/main.py` 加依赖 `verify_token`：当 `settings.api_token` 非空时校验 `Authorization: Bearer <token>`，否则放行（本地模式不变）。
- [ ] **Step 2:** 写测试：配置 token 后无头请求返回 401，带 token 返回 200。
- [ ] **Step 3:** CORS 的 `allow_origins` 改为从 `settings.cors_origins`（逗号分隔）读取，默认保持 `["*"]`。

---

## 自检对照（Self-Review）

- 报告 P0-1（向量死重/中文无效）→ Task 4、5、6
- 报告 P0-2（中文规则信号）→ Task 1、2、3
- 报告 P0-3（SSE 竞态/任务不可恢复）→ Task 7、8
- 报告 P0-4（删除不清理）→ Task 9
- 报告 P0-5（安全边界）→ Task 21（可选）+ 上传/URL 校验见 Task 10
- 报告 P1-6（LLM 健壮性）→ Task 11
- 报告 P1-7（可观测性）→ Task 11（日志）+ Task 20（可选）
- 报告 P1-8（迁移）→ Task 14
- 报告 P1-9（依赖锁定）→ Task 15
- 报告 P1-10（匹配图重复编译）→ Task 12
- 报告 P1-11（N+1）→ Task 13
- 报告 P1-12（评测可移植）→ Task 17
- 报告 P1-13（前端工程）→ Task 16（CI 构建）；App.jsx 拆分留待前端规模继续膨胀时做
- 报告 P1-14（CI/规范）→ Task 16
- 报告 P1-15（README 断链）→ Task 6
- 报告 P1-16（孤儿文件/重复投递）→ Task 10
- 报告 P2（长期增强）→ Task 19、20、21
