# Job Copilot · Phase 2（情报与投递）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 1 核心闭环之上补齐：投递状态机（含非法跳转拦截、跟进建议、提醒）、岗位情报增强（网页搜索、企业研究、市场洞察、批量 JD 导入）、Supervisor 意图识别与路由，以及对应前端看板。

**Architecture:** 复用 Phase 1 的 FastAPI + SQLAlchemy + LangGraph + React 结构。新增 `Application` / `JDReport` 表；投递状态机以「默认转移表 + 每单自定义状态」校验；情报层通过可注入的 `SearchTool`（Tavily，无 Key 时降级为纯 LLM 生成）；市场洞察为确定性聚合（技能频次 / 薪资解析 / 地点与公司统计）；Supervisor 以 LLM 意图分类 + 路由表暴露 `/api/agent/message` 入口。所有新服务保持「llm / search / vector_store 可注入」以支持测试。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / LangGraph / OpenAI SDK / httpx（Tavily）/ React 18 + Vite + Tailwind / pytest。

**前置条件:** Phase 1 已按 `2026-08-04-job-copilot-phase1.md` 完成并全部测试通过。

**项目根目录:** `job-copilot/`。所有相对路径均相对于该目录。

---

## 文件结构总览（Phase 2 新增/修改）

```
job-copilot/
├── app/
│   ├── utils/                      # 新增：共用文本工具
│   │   ├── __init__.py
│   │   └── text.py                 # extract_terms
│   ├── models.py                   # 修改：+ Application、JDReport
│   ├── schemas.py                  # 修改：+ 投递/洞察/报告/意图 schema
│   ├── agents/
│   │   ├── supervisor.py           # 新增：意图分类 + 路由
│   │   └── research_agent.py       # 新增：企业研究/市场洞察提示词
│   ├── tools/
│   │   └── search.py               # 新增：SearchTool（Tavily / 可注入）
│   ├── services/
│   │   ├── application_service.py  # 新增：投递状态机 + 建议 + 提醒
│   │   ├── research_service.py     # 新增：企业研究报告 + 持久化
│   │   └── insight_service.py      # 新增：市场洞察聚合
│   ├── workflow/graph.py           # 修改：改用 utils.text.extract_terms
│   ├── main.py                     # 修改：+ 投递/洞察/研究/批量/Supervisor 端点 + GET /api/jds
│   └── web/src/
│       ├── api.js                  # 修改：+ 投递/洞察/研究/批量/助手函数
│       ├── components/
│       │   ├── JDPanel.jsx         # 修改：+ 批量导入/列表/洞察/企业研究
│       │   ├── MatchPanel.jsx      # 修改：+ 记录投递
│       │   ├── PipelinePanel.jsx   # 新增：投递看板
│       │   └── AgentPanel.jsx      # 新增：助手（Supervisor 入口）
│       └── App.jsx                 # 修改：+ 投递看板/助手 Tab
└── tests/
    ├── test_text_utils.py          # 新增
    ├── test_application_service.py # 新增
    ├── test_search.py              # 新增
    ├── test_research_service.py    # 新增
    ├── test_insight_service.py     # 新增
    ├── test_supervisor.py          # 新增
    └── test_api_phase2.py          # 新增：Phase 2 API 集成
```

**模块边界（Phase 2）：**
- `app/utils/text.py`：纯文本函数，Phase 1 的 `_extract_terms` 迁入，graph.py 保留别名以兼容既有测试。
- `app/services/application_service.py`：唯一投递状态机。对外暴露 `create_application` / `transition` / `register_custom_status` / `list_applications` / `get_reminders` / `to_payload`，不碰 HTTP。
- `app/services/insight_service.py`：确定性聚合，不调用 LLM，输出可直接测试的结构化报告。
- `app/services/research_service.py`：调用 SearchTool + LLM，结果持久化到 `JDReport`。
- `app/agents/supervisor.py`：只做意图分类与路由说明；具体动作仍由既有服务执行。

---

## Milestone A：投递管理

### Task 1: 抽取共用文本工具

**Files:**
- Create: `app/utils/__init__.py`
- Create: `app/utils/text.py`
- Create: `tests/test_text_utils.py`
- Modify: `app/workflow/graph.py`（改用 extract_terms，保留 `_extract_terms` 别名）

- [ ] **Step 1: 写失败测试 `tests/test_text_utils.py`**

```python
from app.utils.text import extract_terms


def test_extract_terms_basic():
    assert extract_terms("Python, LangGraph 与 MySQL") == {"Python", "LangGraph", "MySQL"}


def test_extract_terms_empty():
    assert extract_terms("") == set()


def test_extract_terms_ignores_cjk_only():
    assert extract_terms("招聘实习生") == set()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_text_utils.py -v`
Expected: FAIL（`ModuleNotFoundError: app.utils`）

- [ ] **Step 3: 创建 `app/utils/__init__.py`（空文件）与 `app/utils/text.py`**

```python
import re


def extract_terms(text: str) -> set[str]:
    """提取 ASCII 技能词（Python/LangGraph/MySQL 等）。中文语义由 LLM 层处理。"""
    return set(re.findall(r"[A-Za-z0-9][A-Za-z0-9+#._-]{1,}", text))
```

- [ ] **Step 4: 修改 `app/workflow/graph.py`**

把文件顶部的 `import re` 与 `_extract_terms` 定义替换为：

```python
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.utils.text import extract_terms
```

并把原 `_extract_terms` 函数体替换为别名：

```python
def _extract_terms(text: str) -> set[str]:
    """兼容别名：真实实现见 app/utils/text.py。"""
    return extract_terms(text)
```

- [ ] **Step 5: 运行测试确认通过（含既有回归）**

Run: `pytest tests/test_text_utils.py tests/test_match_workflow.py -v`
Expected: 全部通过（新增 3 个 + 既有 2 个）

- [ ] **Step 6: 提交**

```bash
git add app/utils tests/test_text_utils.py app/workflow/graph.py
git commit -m "refactor: 抽取共用文本工具 extract_terms"
```

### Task 2: Application / JDReport 模型与 Phase 2 Schemas

**Files:**
- Modify: `app/models.py`（+ Application、JDReport）
- Modify: `app/schemas.py`（+ 投递/报告/意图 schema）
- Test: `tests/test_models.py`（追加用例）

- [ ] **Step 1: 在 `tests/test_models.py` 末尾追加失败测试**

```python
def test_application_model(db_session):
    resume = Resume(raw_text="r", structured_json={})
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=80.0)
    db_session.add(match)
    db_session.commit()

    application = Application(
        match_id=match.id,
        current_status="applied",
        status_history_json=[{"status": "applied", "at": "2026-08-01T00:00:00+00:00"}],
        custom_statuses_json={"offer_pending": ["offer"]},
    )
    db_session.add(application)
    db_session.commit()
    loaded = db_session.get(Application, application.id)
    assert loaded.current_status == "applied"
    assert loaded.custom_statuses_json["offer_pending"] == ["offer"]


def test_jd_report_model(db_session):
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={})
    db_session.add(jd)
    db_session.commit()
    report = JDReport(jd_id=jd.id, report_type="company_research", report_json={"company": "京东"})
    db_session.add(report)
    db_session.commit()
    assert db_session.get(JDReport, report.id).report_json["company"] == "京东"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL（`ImportError` / `NameError: Application`）

- [ ] **Step 3: 在 `tests/test_models.py` 顶部更新导入**

```python
from app.models import Application, JD, JDReport, Match, Resume
```

- [ ] **Step 4: 修改 `app/models.py`（追加两个模型）**

在 `Match` 模型之后追加：

```python
class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    current_status: Mapped[str] = mapped_column(String(30), default="applied")
    status_history_json: Mapped[list] = mapped_column(JSON, default=list)
    custom_statuses_json: Mapped[dict] = mapped_column(JSON, default=dict)
    next_action: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class JDReport(Base):
    __tablename__ = "jd_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    jd_id: Mapped[str | None] = mapped_column(ForeignKey("jds.id"), nullable=True)
    report_type: Mapped[str] = mapped_column(String(30))  # company_research | market_insight
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 5: 在 `app/schemas.py` 末尾追加 Phase 2 schema**

```python
class ApplicationCreate(BaseModel):
    match_id: str
    notes: str = ""


class ApplicationTransition(BaseModel):
    target_status: str
    note: str = ""


class CustomStatusCreate(BaseModel):
    status: str
    from_status: str = "applied"
    next: list[str] = []


class CompanyReport(BaseModel):
    company: str = ""
    business_lines: list[str] = []
    interview_process: str = ""
    salary_reference: str = ""
    team_background: str = ""
    tips: list[str] = []
    source_note: str = ""


class Intent(BaseModel):
    intent: str = "help"
    target: str = ""


class AgentMessage(BaseModel):
    message: str
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/test_models.py -v`
Expected: 4 passed（2 旧 + 2 新）

- [ ] **Step 7: 提交**

```bash
git add app/models.py app/schemas.py tests/test_models.py
git commit -m "feat: Application/JDReport 模型与 Phase 2 schema"
```

### Task 3: 投递状态机服务

**Files:**
- Create: `app/services/application_service.py`
- Test: `tests/test_application_service.py`

- [ ] **Step 1: 写失败测试 `tests/test_application_service.py`**

```python
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Application, JD, Match, Resume
from app.services.application_service import (
    create_application,
    follow_up_suggestion,
    get_reminders,
    list_applications,
    register_custom_status,
    transition,
)


def _make_match(db_session):
    resume = Resume(raw_text="r", structured_json={}, status="confirmed")
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=83.0)
    db_session.add(match)
    db_session.commit()
    return match.id


def test_create_application(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id, notes="备注")
    assert app.current_status == "applied"
    assert len(app.status_history_json) == 1
    assert app.notes == "备注"


def test_transition_valid(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    app = transition(db_session, app.id, "screening", note="进入笔试")
    assert app.current_status == "screening"
    assert len(app.status_history_json) == 2


def test_transition_illegal_raises(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    with pytest.raises(ValueError):
        transition(db_session, app.id, "offer")


def test_custom_status_enables_transition(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    app = register_custom_status(db_session, app.id, "offer_pending", "applied", ["offer"])
    assert "offer_pending" in app.custom_statuses_json["applied"]
    app = transition(db_session, app.id, "offer_pending")
    assert app.current_status == "offer_pending"
    app = transition(db_session, app.id, "offer")
    assert app.current_status == "offer"


def test_follow_up_suggestion_by_status():
    old = datetime.now(timezone.utc) - timedelta(days=10)
    applied = Application(
        current_status="applied",
        status_history_json=[{"status": "applied", "at": old.isoformat()}],
    )
    assert "建议" in follow_up_suggestion(applied)
    fresh = Application(
        current_status="applied",
        status_history_json=[{"status": "applied", "at": datetime.now(timezone.utc).isoformat()}],
    )
    assert follow_up_suggestion(fresh) == ""


def test_reminders_include_overdue(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    old = datetime.now(timezone.utc) - timedelta(days=5)
    app.status_history_json = [{"status": "applied", "at": old.isoformat()}]
    db_session.commit()
    reminders = get_reminders(db_session)
    assert any(r["application_id"] == app.id for r in reminders)
    assert list_applications(db_session)[0]["waiting_days"] >= 5
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_application_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.application_service`）

- [ ] **Step 3: 创建 `app/services/application_service.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Application, Match

CORE_STATUSES = ["applied", "screening", "interview", "offer", "accepted", "rejected"]

DEFAULT_TRANSITIONS = {
    "applied": ["screening", "interview", "rejected"],
    "screening": ["interview", "applied", "rejected"],
    "interview": ["offer", "screening", "rejected"],
    "offer": ["accepted", "interview", "rejected"],
    "accepted": [],
    "rejected": ["applied"],
}

REMINDER_THRESHOLD_DAYS = {"applied": 3, "screening": 7, "interview": 5, "offer": 2}


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    db.commit()
    db.refresh(application)
    return application


def allowed_next(application: Application) -> list[str]:
    custom = application.custom_statuses_json.get(application.current_status, [])
    return sorted(set(DEFAULT_TRANSITIONS.get(application.current_status, [])) | set(custom))


def transition(db: Session, app_id: str, target_status: str, note: str = "") -> Application:
    application = db.get(Application, app_id)
    if application is None:
        raise KeyError(f"application not found: {app_id}")
    if target_status not in allowed_next(application):
        raise ValueError(
            f"非法状态跳转: {application.current_status} -> {target_status}"
        )
    history = list(application.status_history_json)
    history.append({"status": target_status, "at": _now().isoformat(), "note": note})
    application.status_history_json = history
    application.current_status = target_status
    application.updated_at = _now()
    db.commit()
    db.refresh(application)
    return application


def register_custom_status(
    db: Session, app_id: str, status: str, from_status: str, next_statuses: list[str]
) -> Application:
    application = db.get(Application, app_id)
    if application is None:
        raise KeyError(f"application not found: {app_id}")
    if status in CORE_STATUSES:
        raise ValueError(f"不能覆盖核心状态: {status}")
    custom = dict(application.custom_statuses_json)
    custom.setdefault(from_status, [])
    custom[from_status].append(status)
    custom[status] = list(next_statuses)
    application.custom_statuses_json = custom
    db.commit()
    db.refresh(application)
    return application


def waiting_days(application: Application) -> int:
    history = application.status_history_json
    if not history:
        return 0
    last_at = datetime.fromisoformat(history[-1]["at"])
    return max((_now() - last_at).days, 0)


def follow_up_suggestion(application: Application) -> str:
    status = application.current_status
    days = waiting_days(application)
    if status == "applied" and days >= REMINDER_THRESHOLD_DAYS["applied"]:
        return f"已投递 {days} 天，建议礼貌询问招聘进度"
    if status == "screening" and days >= REMINDER_THRESHOLD_DAYS["screening"]:
        return f"筛选中已 {days} 天，可主动补充材料或询问流程"
    if status == "interview" and days >= REMINDER_THRESHOLD_DAYS["interview"]:
        return f"面试后 {days} 天未反馈，建议发送感谢信并询问结果"
    if status == "offer" and days >= REMINDER_THRESHOLD_DAYS["offer"]:
        return f"收到 Offer 已 {days} 天，建议确认接受时间与入职材料"
    return ""


def to_payload(application: Application) -> dict:
    return {
        "application_id": application.id,
        "match_id": application.match_id,
        "current_status": application.current_status,
        "status_history": application.status_history_json,
        "allowed_next": allowed_next(application),
        "waiting_days": waiting_days(application),
        "suggestion": follow_up_suggestion(application),
        "custom_statuses": application.custom_statuses_json,
        "notes": application.notes,
        "next_action": application.next_action,
        "reminder_at": application.reminder_at.isoformat() if application.reminder_at else None,
        "created_at": application.created_at.isoformat(),
    }


def list_applications(db: Session) -> list[dict]:
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    return [to_payload(a) for a in apps]


def get_reminders(db: Session) -> list[dict]:
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    reminders = []
    for a in apps:
        if a.reminder_at and a.reminder_at <= _now():
            reminders.append(to_payload(a))
        elif follow_up_suggestion(a):
            reminders.append(to_payload(a))
    return reminders
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_application_service.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add app/services/application_service.py tests/test_application_service.py
git commit -m "feat: 投递状态机（校验/历史/建议/提醒）"
```

### Task 4: 投递 API 端点

**Files:**
- Modify: `app/main.py`（+ 投递端点与导入）
- Test: `tests/test_api_phase2.py`（先建本任务的投递用例）

- [ ] **Step 1: 写失败测试 `tests/test_api_phase2.py`（本任务先写投递相关用例，后续任务追加）**

```python
from app.models import JD, Match, Resume


def _make_match(db_session):
    resume = Resume(raw_text="r", structured_json={"skills": ["Python"]}, status="confirmed")
    jd = JD(
        company="京东",
        title="LLM 应用开发实习生",
        raw_text="j",
        structured_json={
            "company": "京东",
            "title": "LLM 应用开发实习生",
            "location": "北京",
            "salary": "20-40K·14薪",
            "requirements": ["Python", "LangGraph"],
        },
    )
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=83.0)
    db_session.add(match)
    db_session.commit()
    return match.id, jd.id


def test_application_flow(client, db_session):
    match_id, _ = _make_match(db_session)
    res = client.post("/api/applications", json={"match_id": match_id, "notes": "备注"})
    assert res.status_code == 200
    app_id = res.json()["application_id"]
    assert res.json()["current_status"] == "applied"

    res2 = client.post(
        f"/api/applications/{app_id}/status",
        json={"target_status": "screening", "note": "进入笔试"},
    )
    assert res2.status_code == 200
    assert res2.json()["current_status"] == "screening"
    assert len(res2.json()["status_history"]) == 2

    res3 = client.post(f"/api/applications/{app_id}/status", json={"target_status": "offer"})
    assert res3.status_code == 422


def test_application_custom_status(client, db_session):
    match_id, _ = _make_match(db_session)
    app_id = client.post("/api/applications", json={"match_id": match_id}).json()["application_id"]
    res = client.post(
        f"/api/applications/{app_id}/custom-statuses",
        json={"status": "offer_pending", "from_status": "applied", "next": ["offer"]},
    )
    assert res.status_code == 200
    assert "offer_pending" in res.json()["custom_statuses"]["applied"]
    res2 = client.post(f"/api/applications/{app_id}/status", json={"target_status": "offer_pending"})
    assert res2.status_code == 200
    assert res2.json()["current_status"] == "offer_pending"


def test_application_list_and_reminders(client, db_session):
    match_id, _ = _make_match(db_session)
    client.post("/api/applications", json={"match_id": match_id})
    res = client.get("/api/applications")
    assert res.status_code == 200
    assert len(res.json()["applications"]) == 1
    res2 = client.get("/api/applications/reminders")
    assert res2.status_code == 200
    assert isinstance(res2.json()["reminders"], list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api_phase2.py -v`
Expected: FAIL（404，端点不存在）

- [ ] **Step 3: 修改 `app/main.py`**

在文件头部导入区追加：

```python
from app.schemas import (
    AgentMessage,
    ApplicationCreate,
    ApplicationTransition,
    CoverLetterRequest,
    CustomStatusCreate,
    MatchRequest,
)
from app.services import (
    application_service,
    cover_letter_service,
    jd_service,
    match_service,
    resume_service,
)
```

（原 `from app.schemas import CoverLetterRequest, MatchRequest` 与 `from app.services import ...` 两行删除，由上面的合并导入替代。）

在 `/api/matches/{match_id}/cover-letter` 端点之后追加投递端点：

```python
@app.post("/api/applications")
def create_application(payload: ApplicationCreate, db: Session = Depends(get_session)):
    try:
        application = application_service.create_application(db, payload.match_id, payload.notes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return application_service.to_payload(application)


@app.get("/api/applications")
def list_applications(db: Session = Depends(get_session)):
    return {"applications": application_service.list_applications(db)}


@app.get("/api/applications/reminders")
def application_reminders(db: Session = Depends(get_session)):
    return {"reminders": application_service.get_reminders(db)}


@app.post("/api/applications/{app_id}/status")
def transition_application(
    app_id: str, payload: ApplicationTransition, db: Session = Depends(get_session)
):
    try:
        application = application_service.transition(
            db, app_id, payload.target_status, payload.note
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return application_service.to_payload(application)


@app.post("/api/applications/{app_id}/custom-statuses")
def add_custom_status(
    app_id: str, payload: CustomStatusCreate, db: Session = Depends(get_session)
):
    try:
        application = application_service.register_custom_status(
            db, app_id, payload.status, payload.from_status, payload.next
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return application_service.to_payload(application)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_api_phase2.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add app/main.py tests/test_api_phase2.py
git commit -m "feat: 投递 API 端点（状态机/自定义状态/提醒）"
```

### Task 5: 投递看板前端

**Files:**
- Create: `app/web/src/components/PipelinePanel.jsx`
- Modify: `app/web/src/App.jsx`（+ 投递看板 Tab）
- Modify: `app/web/src/api.js`（+ 投递相关函数）

- [ ] **Step 1: 在 `app/web/src/api.js` 末尾追加投递函数**

```js
export async function createApplication(matchId, notes = '') {
  const res = await fetch('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ match_id: matchId, notes })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listApplications() {
  const res = await fetch('/api/applications')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function getReminders() {
  const res = await fetch('/api/applications/reminders')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function transitionApplication(appId, targetStatus, note = '') {
  const res = await fetch(`/api/applications/${appId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_status: targetStatus, note })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function registerCustomStatus(appId, status, fromStatus, next) {
  const res = await fetch(`/api/applications/${appId}/custom-statuses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, from_status: fromStatus, next })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
```

- [ ] **Step 2: 创建 `app/web/src/components/PipelinePanel.jsx`**

```jsx
import { useEffect, useState } from 'react'
import {
  getReminders,
  listApplications,
  registerCustomStatus,
  transitionApplication
} from '../api.js'

function CustomStatusForm({ appId, onDone }) {
  const [status, setStatus] = useState('')
  const [from, setFrom] = useState('applied')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async () => {
    if (!status.trim()) return
    setBusy(true)
    setError('')
    try {
      await registerCustomStatus(
        appId,
        status.trim(),
        from,
        next.split(',').map((s) => s.trim()).filter(Boolean)
      )
      setStatus('')
      setNext('')
      onDone()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex gap-2 flex-wrap items-center text-xs">
      <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="新状态名，如 offer_pending" className="border rounded px-2 py-1" />
      <select value={from} onChange={(e) => setFrom(e.target.value)} className="border rounded px-2 py-1">
        <option value="applied">applied</option>
        <option value="screening">screening</option>
        <option value="interview">interview</option>
        <option value="offer">offer</option>
      </select>
      <input value={next} onChange={(e) => setNext(e.target.value)} placeholder="下一步（逗号分隔）" className="border rounded px-2 py-1" />
      <button onClick={handleSubmit} disabled={busy} className="px-3 py-1 bg-slate-700 text-white rounded disabled:opacity-50">
        注册
      </button>
      {error && <span className="text-red-600">{error}</span>}
    </div>
  )
}

export default function PipelinePanel() {
  const [applications, setApplications] = useState([])
  const [reminderIds, setReminderIds] = useState([])
  const [message, setMessage] = useState('')

  const refresh = async () => {
    const [data, r] = await Promise.all([listApplications(), getReminders()])
    setApplications(data.applications)
    setReminderIds(r.reminders.map((x) => x.application_id))
  }

  useEffect(() => {
    refresh().catch((e) => setMessage(`加载失败：${e.message}`))
  }, [])

  const handleTransition = async (appId, target) => {
    try {
      await transitionApplication(appId, target)
      await refresh()
    } catch (e) {
      setMessage(`状态变更失败：${e.message}`)
    }
  }

  return (
    <div className="space-y-4">
      {message && <p className="text-sm text-red-600">{message}</p>}
      {applications.length === 0 && (
        <p className="text-sm text-slate-500">还没有投递记录，去「匹配与自荐信」页生成匹配后点击「记录投递」。</p>
      )}
      {applications.map((a) => (
        <div key={a.application_id} className={`bg-white border rounded-lg p-4 space-y-2 ${reminderIds.includes(a.application_id) ? 'border-amber-400' : ''}`}>
          <div className="flex justify-between items-center">
            <div>
              <span className="font-mono text-xs text-slate-500">{a.match_id}</span>
              <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{a.current_status}</span>
              {reminderIds.includes(a.application_id) && (
                <span className="ml-2 px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">提醒</span>
              )}
            </div>
            <span className="text-xs text-slate-500">等待 {a.waiting_days} 天</span>
          </div>
          {a.suggestion && <p className="text-sm text-amber-700">{a.suggestion}</p>}
          <div className="flex gap-2 flex-wrap">
            {a.allowed_next.map((t) => (
              <button key={t} onClick={() => handleTransition(a.application_id, t)} className="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded text-sm">
                转为 {t}
              </button>
            ))}
          </div>
          {a.notes && <p className="text-xs text-slate-500">备注：{a.notes}</p>}
          <CustomStatusForm appId={a.application_id} onDone={refresh} />
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: 修改 `app/web/src/App.jsx`（注册投递看板 Tab）**

导入并加入 TABS：

```jsx
import PipelinePanel from './components/PipelinePanel.jsx'

const TABS = [
  { key: 'resume', label: '简历', component: ResumePanel },
  { key: 'jd', label: '岗位 JD', component: JDPanel },
  { key: 'match', label: '匹配与自荐信', component: MatchPanel },
  { key: 'pipeline', label: '投递看板', component: PipelinePanel }
]
```

- [ ] **Step 4: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add app/web/src/api.js app/web/src/components/PipelinePanel.jsx app/web/src/App.jsx
git commit -m "feat: 投递看板前端"
```

---

## Milestone B：岗位情报增强

### Task 6: SearchTool（Tavily / 可注入 / 无 Key 降级）

**Files:**
- Modify: `app/config.py`（+ search 配置）
- Create: `app/tools/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: 修改 `app/config.py`（追加搜索配置）**

```python
    search_api_key: str = ""
    search_provider: str = "tavily"
```

（追加在 `upload_dir` 之后。）

- [ ] **Step 2: 写失败测试 `tests/test_search.py`**

```python
from app.tools.search import SearchTool


def test_search_no_key_returns_empty():
    tool = SearchTool(api_key="")
    assert tool.search("京东 面试") == []


def test_search_tavily(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {"title": "京东面试攻略", "url": "https://example.com", "content": "两轮技术面"}
                ]
            }

    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResponse())
    tool = SearchTool(api_key="fake-key")
    results = tool.search("京东 面试", top_k=5)
    assert results[0]["title"] == "京东面试攻略"
    assert results[0]["url"] == "https://example.com"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_search.py -v`
Expected: FAIL（`ModuleNotFoundError: app.tools.search`）

- [ ] **Step 4: 创建 `app/tools/search.py`**

```python
import httpx

from app.config import settings


class SearchTool:
    """网页搜索工具。provider=tavily 时调用 API；未配置 Key 时返回空列表（调用方降级）。"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else settings.search_api_key

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.api_key:
            return []
        response = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": self.api_key, "query": query, "max_results": top_k},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in data.get("results", [])[:top_k]
        ]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_search.py -v`
Expected: 2 passed

- [ ] **Step 6: 提交**

```bash
git add app/config.py app/tools/search.py tests/test_search.py
git commit -m "feat: SearchTool（Tavily/可注入/降级）"
```

### Task 7: 企业研究服务与 API

**Files:**
- Create: `app/agents/research_agent.py`（提示词封装）
- Create: `app/services/research_service.py`
- Modify: `app/main.py`（+ 研究端点）
- Test: `tests/test_research_service.py`
- Test: `tests/test_api_phase2.py`（追加研究用例）

- [ ] **Step 1: 写失败测试 `tests/test_research_service.py`**

```python
from app.models import JD, JDReport
from app.services.research_service import generate_company_report


class FakeSearch:
    def search(self, query, top_k=5):
        return [{"title": "t", "url": "u", "content": "面试流程：两轮技术面+一轮 HR"}]


class FakeLLM:
    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(
            {
                "company": "京东",
                "business_lines": ["零售", "物流"],
                "interview_process": "两轮技术面+一轮 HR",
                "salary_reference": "20-40K",
                "team_background": "大模型团队",
                "tips": ["准备 RAG 项目经历"],
                "source_note": "基于搜索与模型知识",
            }
        ).model_dump()


def test_generate_company_report_persists(db_session):
    jd = JD(
        company="京东",
        title="LLM 应用开发实习生",
        raw_text="j",
        structured_json={"company": "京东", "title": "LLM 应用开发实习生"},
    )
    db_session.add(jd)
    db_session.commit()

    report = generate_company_report(db_session, jd.id, llm=FakeLLM(), search=FakeSearch())
    assert report["company"] == "京东"
    assert report["interview_process"] == "两轮技术面+一轮 HR"
    stored = db_session.query(JDReport).filter_by(jd_id=jd.id).one()
    assert stored.report_type == "company_research"
    assert stored.report_json["company"] == "京东"


def test_generate_company_report_no_search(db_session):
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={"company": "京东"})
    db_session.add(jd)
    db_session.commit()
    report = generate_company_report(
        db_session, jd.id, llm=FakeLLM(), search=FakeSearchEmpty()
    )
    assert report["source_note"]  # 无搜索结果时提示降级


class FakeSearchEmpty:
    def search(self, query, top_k=5):
        return []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_research_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.agents.research_agent`）

- [ ] **Step 3: 创建 `app/agents/research_agent.py`**

```python
from app.llm import LLMService
from app.schemas import CompanyReport


def generate_report(
    company: str,
    title: str,
    jd_summary: str,
    snippets: list[dict],
    llm: LLMService,
) -> dict:
    """基于公司/JD/搜索片段生成企业研究报告。"""
    source_note = ""
    if not snippets:
        source_note = "未获取到搜索结果，报告基于模型知识生成，仅供参考"
    snippet_text = "\n".join(
        f"- {s.get('title', '')}: {s.get('content', '')[:200]}" for s in snippets[:5]
    )
    messages = [
        {
            "role": "system",
            "content": "你是求职情报分析师。基于已知信息生成企业研究报告，缺失信息如实说明，不要编造。",
        },
        {
            "role": "user",
            "content": (
                f"公司：{company}\n岗位：{title}\nJD 摘要：{jd_summary}\n"
                f"搜索片段：\n{snippet_text or '（无）'}\n"
                "输出 JSON：company(公司名)、business_lines(业务线)、interview_process(面试流程)、"
                "salary_reference(薪资参考)、team_background(团队背景)、tips(求职建议，最多 3 条)、"
                f"source_note(信息源说明，此处填：{source_note})"
            ),
        },
    ]
    data = llm.complete_structured(messages, CompanyReport)
    if not data["source_note"]:
        data["source_note"] = source_note
    return data
```

- [ ] **Step 4: 创建 `app/services/research_service.py`**

```python
import json

from sqlalchemy.orm import Session

from app.agents.research_agent import generate_report
from app.llm import LLMService
from app.models import JD, JDReport
from app.tools.search import SearchTool


def generate_company_report(
    db: Session,
    jd_id: str,
    llm: LLMService | None = None,
    search: SearchTool | None = None,
) -> dict:
    jd = db.get(JD, jd_id)
    if jd is None:
        raise KeyError(f"jd not found: {jd_id}")
    llm = llm or LLMService()
    search = search or SearchTool()
    snippets = search.search(f"{jd.company} 面试流程 薪资 团队 招聘", top_k=5)
    report = generate_report(
        company=jd.company or jd.structured_json.get("company", ""),
        title=jd.title or jd.structured_json.get("title", ""),
        jd_summary=json.dumps(jd.structured_json, ensure_ascii=False)[:2000],
        snippets=snippets,
        llm=llm,
    )
    db.add(JDReport(jd_id=jd_id, report_type="company_research", report_json=report))
    db.commit()
    return report
```

- [ ] **Step 5: 修改 `app/main.py`（+ 研究端点与 GET /api/jds）**

在 `/api/jds` 的 POST 端点之后追加：

```python
@app.get("/api/jds")
def list_jds(db: Session = Depends(get_session)):
    from app.models import JD

    jds = db.query(JD).order_by(JD.created_at.desc()).limit(50).all()
    return {
        "jds": [
            {
                "jd_id": jd.id,
                "company": jd.company,
                "title": jd.title,
                "source_type": jd.source_type,
            }
            for jd in jds
        ]
    }


@app.post("/api/jds/{jd_id}/research")
def company_research(jd_id: str, db: Session = Depends(get_session)):
    try:
        report = research_service.generate_company_report(db, jd_id, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"report": report}
```

同时在导入区追加：

```python
from app.services import research_service
```

- [ ] **Step 6: 在 `tests/test_api_phase2.py` 末尾追加研究用例**

```python
def test_company_research_endpoint(client, db_session, monkeypatch):
    import app.main as main_module

    class FakeLLM:
        def complete_structured(self, messages, schema, max_tokens=2000):
            return schema.model_validate(
                {
                    "company": "京东",
                    "business_lines": ["零售", "物流"],
                    "interview_process": "两轮技术面+一轮 HR",
                    "salary_reference": "20-40K",
                    "team_background": "大模型团队",
                    "tips": ["准备 RAG 项目经历"],
                    "source_note": "基于搜索与模型知识",
                }
            ).model_dump()

    monkeypatch.setattr(main_module, "llm", FakeLLM())
    _, jd_id = _make_match(db_session)
    res = client.post(f"/api/jds/{jd_id}/research")
    assert res.status_code == 200
    assert res.json()["report"]["company"] == "京东"


def test_list_jds(client, db_session):
    _, jd_id = _make_match(db_session)
    res = client.get("/api/jds")
    assert res.status_code == 200
    assert any(jd["jd_id"] == jd_id for jd in res.json()["jds"])
```

- [ ] **Step 7: 运行测试确认通过**

Run: `pytest tests/test_research_service.py tests/test_api_phase2.py -v`
Expected: 全部通过

- [ ] **Step 8: 提交**

```bash
git add app/agents/research_agent.py app/services/research_service.py app/main.py tests/test_research_service.py tests/test_api_phase2.py
git commit -m "feat: 企业研究服务与 API"
```

### Task 8: 市场洞察服务 + 批量 JD 导入 + JD 列表 API

**Files:**
- Create: `app/services/insight_service.py`
- Modify: `app/main.py`（+ 批量导入与洞察端点）
- Test: `tests/test_insight_service.py`
- Test: `tests/test_api_phase2.py`（追加批量/洞察用例）

- [ ] **Step 1: 写失败测试 `tests/test_insight_service.py`**

```python
from app.models import JD
from app.services.insight_service import generate_market_insight, parse_salary


def test_parse_salary():
    assert parse_salary("20-40K·14薪") == (20.0, 40.0)
    assert parse_salary("2-4万·14薪") == (20.0, 40.0)
    assert parse_salary("面议") is None
    assert parse_salary("") is None


def test_generate_market_insight(db_session):
    jd1 = JD(
        company="京东",
        title="A",
        raw_text="a",
        structured_json={
            "requirements": ["Python LangGraph"],
            "location": "北京",
            "salary": "20-40K·14薪",
        },
    )
    jd2 = JD(
        company="字节",
        title="B",
        raw_text="b",
        structured_json={
            "requirements": ["Python RAG"],
            "location": "上海",
            "salary": "30-50K·15薪",
        },
    )
    db_session.add_all([jd1, jd2])
    db_session.commit()

    report = generate_market_insight(db_session)
    assert report["total_jds"] == 2
    assert report["top_skills"][0]["skill"] == "Python"
    assert report["top_skills"][0]["count"] == 2
    assert report["salary_stats"]["median"] == 45.0
    assert report["location_counts"]["北京"] == 1
    assert report["company_counts"]["京东"] == 1
    assert report["generated_at"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_insight_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.insight_service`）

- [ ] **Step 3: 创建 `app/services/insight_service.py`**

```python
import re
import statistics
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import JD
from app.utils.text import extract_terms

SALARY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)\s*([kK万])")


def parse_salary(text: str) -> tuple[float, float] | None:
    """解析薪资文本为 (下限k, 上限k)；无法解析返回 None。"""
    m = SALARY_RE.search(text or "")
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    if m.group(3) == "万":
        lo, hi = lo * 10, hi * 10
    return lo, hi


def generate_market_insight(db: Session) -> dict:
    """聚合全部 JD：技能频次、薪资统计、地点与公司分布。确定性输出，不调用 LLM。"""
    jds = db.query(JD).all()
    skills: Counter = Counter()
    locations: Counter = Counter()
    companies: Counter = Counter()
    salary_maxes: list[float] = []
    salary_mins: list[float] = []

    for jd in jds:
        structured = jd.structured_json
        for field in ("requirements", "responsibilities"):
            for item in structured.get(field, []):
                for term in extract_terms(item):
                    if len(term) >= 2:
                        skills[term] += 1
        locations[structured.get("location", "未知")] += 1
        companies[jd.company or "未知"] += 1
        parsed = parse_salary(structured.get("salary", ""))
        if parsed:
            salary_mins.append(parsed[0])
            salary_maxes.append(parsed[1])

    salary_stats = {}
    if salary_maxes:
        salary_stats = {
            "min": min(salary_mins),
            "median": statistics.median(salary_maxes),
            "max": max(salary_maxes),
        }
    return {
        "total_jds": len(jds),
        "top_skills": [
            {"skill": skill, "count": count} for skill, count in skills.most_common(10)
        ],
        "salary_stats": salary_stats,
        "location_counts": dict(locations),
        "company_counts": dict(companies),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: 修改 `app/main.py`（+ 批量导入与洞察端点）**

在 `list_jds` 端点之后追加：

```python
@app.post("/api/jds/batch")
def create_jds_batch(payload: dict, db: Session = Depends(get_session)):
    texts = payload.get("texts", [])
    if not isinstance(texts, list) or not texts:
        raise HTTPException(status_code=400, detail="texts 必填且为非空数组")
    jd_ids = []
    for text in texts:
        jd = jd_service.create_jd_from_text(db, text, vector_store, llm=llm)
        jd_ids.append(jd.id)
    return {"jd_ids": jd_ids}


@app.post("/api/insights/market")
def market_insight(db: Session = Depends(get_session)):
    from app.models import JDReport

    report = insight_service.generate_market_insight(db)
    db.add(JDReport(report_type="market_insight", jd_id=None, report_json=report))
    db.commit()
    return {"report": report}
```

同时在导入区追加：

```python
from app.services import insight_service
```

- [ ] **Step 5: 在 `tests/test_api_phase2.py` 末尾追加批量/洞察用例**

```python
def test_batch_jds(client):
    res = client.post("/api/jds/batch", json={"texts": ["JD1 招 Python 实习生", "JD2 招 RAG 工程师"]})
    assert res.status_code == 200
    assert len(res.json()["jd_ids"]) == 2


def test_batch_jds_empty_400(client):
    res = client.post("/api/jds/batch", json={"texts": []})
    assert res.status_code == 400


def test_market_insight_endpoint(client, db_session):
    _, jd_id = _make_match(db_session)
    res = client.post("/api/insights/market")
    assert res.status_code == 200
    report = res.json()["report"]
    assert report["total_jds"] == 1
    assert report["company_counts"]["京东"] == 1
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/test_insight_service.py tests/test_api_phase2.py -v`
Expected: 全部通过

- [ ] **Step 7: 提交**

```bash
git add app/services/insight_service.py app/main.py tests/test_insight_service.py tests/test_api_phase2.py
git commit -m "feat: 市场洞察聚合与批量 JD 导入"
```

### Task 9: JD 面板增强（批量导入 / 列表 / 洞察 / 企业研究）

**Files:**
- Modify: `app/web/src/api.js`（+ JD 列表/批量/洞察/研究函数）
- Modify: `app/web/src/components/JDPanel.jsx`（整体重写）

- [ ] **Step 1: 在 `app/web/src/api.js` 末尾追加情报函数**

```js
export async function createJDsBatch(texts) {
  const res = await fetch('/api/jds/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listJDs() {
  const res = await fetch('/api/jds')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function generateCompanyResearch(jdId) {
  const res = await fetch(`/api/jds/${jdId}/research`, { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function generateMarketInsight() {
  const res = await fetch('/api/insights/market', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
```

- [ ] **Step 2: 重写 `app/web/src/components/JDPanel.jsx`**

```jsx
import { useEffect, useState } from 'react'
import {
  createJD,
  createJDsBatch,
  generateCompanyResearch,
  generateMarketInsight,
  listJDs
} from '../api.js'

export default function JDPanel({ onJDAdded }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [batchText, setBatchText] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [jds, setJds] = useState([])
  const [insight, setInsight] = useState(null)
  const [research, setResearch] = useState({})
  const [busyJdId, setBusyJdId] = useState('')

  const refreshJds = async () => {
    const data = await listJDs()
    setJds(data.jds)
  }

  useEffect(() => {
    refreshJds().catch((e) => setMessage(`加载 JD 列表失败：${e.message}`))
  }, [])

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
      await refreshJds()
    } catch (e) {
      setMessage(`录入失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleBatch = async () => {
    const texts = batchText.split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean)
    if (texts.length === 0) {
      setMessage('请用空行分隔多条 JD')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      const data = await createJDsBatch(texts)
      setMessage(`批量录入成功：${data.jd_ids.length} 条`)
      setBatchText('')
      await refreshJds()
    } catch (e) {
      setMessage(`批量录入失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleInsight = async () => {
    setBusy(true)
    setMessage('')
    try {
      const data = await generateMarketInsight()
      setInsight(data.report)
    } catch (e) {
      setMessage(`洞察生成失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleResearch = async (jdId) => {
    setBusyJdId(jdId)
    try {
      const data = await generateCompanyResearch(jdId)
      setResearch((prev) => ({ ...prev, [jdId]: data.report }))
    } catch (e) {
      setMessage(`企业研究失败：${e.message}`)
    } finally {
      setBusyJdId('')
    }
  }

  const tabClass = (active) =>
    `px-4 py-2 rounded-lg text-sm ${active ? 'bg-blue-600 text-white' : 'bg-slate-100 hover:bg-slate-200'}`

  return (
    <div className="space-y-6">
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <button onClick={() => setMode('text')} className={tabClass(mode === 'text')}>粘贴文本</button>
          <button onClick={() => setMode('url')} className={tabClass(mode === 'url')}>URL 抓取</button>
        </div>
        {mode === 'text' ? (
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} placeholder="粘贴 JD 全文" className="w-full border rounded-lg p-3 text-sm" />
        ) : (
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" className="w-full border rounded-lg p-3 text-sm" />
        )}
        <button onClick={handleAdd} disabled={busy || (mode === 'text' ? !text.trim() : !url.trim())} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
          {busy ? '录入中…' : '录入 JD'}
        </button>
      </div>

      <div className="bg-white border rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold">批量导入（空行分隔多条 JD）</h2>
        <textarea value={batchText} onChange={(e) => setBatchText(e.target.value)} rows={8} placeholder="JD1 全文…\n\nJD2 全文…" className="w-full border rounded-lg p-3 text-sm" />
        <button onClick={handleBatch} disabled={busy} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
          {busy ? '批量录入中…' : '批量录入'}
        </button>
      </div>

      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">市场洞察</h2>
          <button onClick={handleInsight} disabled={busy} className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
            生成洞察报告
          </button>
        </div>
        {insight && (
          <div className="text-xs space-y-2">
            <p>共 {insight.total_jds} 条 JD</p>
            <p>热门技能：{insight.top_skills.map((s) => `${s.skill}(${s.count})`).join('、')}</p>
            {insight.salary_stats.median && (
              <p>薪资参考：中位 {insight.salary_stats.median}k / 区间 {insight.salary_stats.min}-{insight.salary_stats.max}k</p>
            )}
            <p>城市分布：{JSON.stringify(insight.location_counts)}</p>
            <p>公司分布：{JSON.stringify(insight.company_counts)}</p>
          </div>
        )}
      </div>

      <div className="bg-white border rounded-lg p-4 space-y-2">
        <h2 className="text-sm font-semibold">JD 列表（{jds.length}）</h2>
        {jds.length === 0 && <p className="text-xs text-slate-500">暂无 JD</p>}
        {jds.map((jd) => (
          <div key={jd.jd_id} className="border rounded-lg p-3 space-y-2">
            <div className="flex justify-between items-center">
              <div>
                <span className="font-semibold text-sm">{jd.company} · {jd.title}</span>
                <span className="ml-2 font-mono text-xs text-slate-400">{jd.jd_id}</span>
              </div>
              <button onClick={() => handleResearch(jd.jd_id)} disabled={busyJdId === jd.jd_id} className="px-3 py-1 bg-slate-700 text-white rounded text-xs disabled:opacity-50">
                {busyJdId === jd.jd_id ? '研究中…' : '企业研究'}
              </button>
            </div>
            {research[jd.jd_id] && (
              <div className="text-xs bg-slate-50 rounded p-3 space-y-1">
                <p>面试流程：{research[jd.jd_id].interview_process || '（未知）'}</p>
                <p>薪资参考：{research[jd.jd_id].salary_reference || '（未知）'}</p>
                <p>团队背景：{research[jd.jd_id].team_background || '（未知）'}</p>
                {research[jd.jd_id].source_note && <p className="text-amber-600">{research[jd.jd_id].source_note}</p>}
              </div>
            )}
          </div>
        ))}
      </div>

      {message && <p className="text-sm text-slate-600">{message}</p>}
    </div>
  )
}
```

- [ ] **Step 3: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add app/web/src/api.js app/web/src/components/JDPanel.jsx
git commit -m "feat: JD 面板批量导入/列表/洞察/企业研究"
```

---

## Milestone C：Supervisor 与助手入口

### Task 10: Supervisor 意图分类与路由

**Files:**
- Create: `app/agents/supervisor.py`
- Modify: `app/main.py`（+ `/api/agent/message`）
- Test: `tests/test_supervisor.py`
- Test: `tests/test_api_phase2.py`（追加助手用例）

- [ ] **Step 1: 写失败测试 `tests/test_supervisor.py`**

```python
from app.agents.supervisor import classify_intent, handle_message


class FakeLLMIntent:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def test_classify_intent():
    llm = FakeLLMIntent({"intent": "market_insight", "target": ""})
    result = classify_intent("分析近期岗位趋势", llm)
    assert result["intent"] == "market_insight"


def test_classify_help_intent():
    llm = FakeLLMIntent({"intent": "help", "target": ""})
    result = classify_intent("你好", llm)
    assert result["intent"] == "help"


def test_handle_message_guidance_for_jd():
    llm = FakeLLMIntent({"intent": "jd_add", "target": ""})
    result = handle_message(None, "帮我加一条 JD", llm)
    assert result["intent"] == "jd_add"
    assert "粘贴" in result["message"]


def test_handle_message_market_insight(db_session):
    llm = FakeLLMIntent({"intent": "market_insight", "target": ""})
    result = handle_message(db_session, "分析趋势", llm)
    assert result["intent"] == "market_insight"
    assert result["payload"]["report"]["total_jds"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_supervisor.py -v`
Expected: FAIL（`ModuleNotFoundError: app.agents.supervisor`）

- [ ] **Step 3: 创建 `app/agents/supervisor.py`**

```python
from sqlalchemy.orm import Session

from app.llm import LLMService
from app.schemas import Intent
from app.services import insight_service

INTENT_PROMPT = (
    "你是 Job Copilot 的意图识别器。把用户消息分类为以下之一：\n"
    "resume_upload / jd_add / match / cover_letter / company_research / market_insight / "
    "application / help\n"
    "示例：\n"
    "- '我要上传简历' -> resume_upload\n"
    "- '帮我加一条 JD' -> jd_add\n"
    "- '匹配一下这个岗位' -> match\n"
    "- '生成自荐信' -> cover_letter\n"
    "- '查一下这家公司的面试流程' -> company_research\n"
    "- '分析近期岗位趋势' -> market_insight\n"
    "- '记录一下投递' -> application\n"
    "- 其他 -> help\n"
    "用户消息：{message}\n"
    '输出 JSON：{{"intent": "...", "target": "公司或岗位名，可为空"}}'
)

INTENT_GUIDANCE = {
    "resume_upload": "请上传简历 PDF，系统会解析并生成结构化简历。",
    "jd_add": "请在岗位 JD 页粘贴 JD 文本或填写 URL。",
    "match": "请进入「匹配与自荐信」页发起匹配。",
    "cover_letter": "先生成匹配结果，然后点击「生成自荐信」。",
    "company_research": "请在岗位 JD 列表中选择一条 JD，点击「企业研究」。",
    "market_insight": "已生成市场洞察报告。",
    "application": "请在投递看板中记录投递状态。",
    "help": "我可以帮你管理简历、JD、匹配、自荐信、企业研究与投递状态。",
}


def classify_intent(message: str, llm: LLMService | None = None) -> dict:
    llm = llm or LLMService()
    prompt = INTENT_PROMPT.format(message=message[:2000])
    return llm.complete_structured([{"role": "user", "content": prompt}], Intent)


def handle_message(
    db: Session | None,
    message: str,
    llm: LLMService | None = None,
) -> dict:
    """意图分类 + 路由。market_insight 直接执行，其余返回引导。"""
    intent = classify_intent(message, llm)["intent"]
    if intent == "market_insight" and db is not None:
        report = insight_service.generate_market_insight(db)
        return {
            "intent": intent,
            "message": INTENT_GUIDANCE[intent],
            "payload": {"report": report},
        }
    return {
        "intent": intent,
        "message": INTENT_GUIDANCE.get(intent, INTENT_GUIDANCE["help"]),
        "payload": {},
    }
```

- [ ] **Step 4: 修改 `app/main.py`（+ 助手端点）**

在文件末尾（静态托管挂载之前）追加：

```python
@app.post("/api/agent/message")
def agent_message(payload: AgentMessage, db: Session = Depends(get_session)):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 必填")
    return supervisor_agent.handle_message(db, message, llm=llm)
```

同时在导入区追加：

```python
from app.agents import supervisor as supervisor_agent
```

- [ ] **Step 5: 在 `tests/test_api_phase2.py` 末尾追加助手用例**

```python
def test_agent_message_endpoint(client, monkeypatch):
    import app.main as main_module

    class FakeLLM:
        def complete_structured(self, messages, schema, max_tokens=2000):
            return schema.model_validate({"intent": "help", "target": ""}).model_dump()

    monkeypatch.setattr(main_module, "llm", FakeLLM())
    res = client.post("/api/agent/message", json={"message": "你好"})
    assert res.status_code == 200
    assert res.json()["intent"] == "help"


def test_agent_message_empty_400(client):
    res = client.post("/api/agent/message", json={"message": "  "})
    assert res.status_code == 400
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/test_supervisor.py tests/test_api_phase2.py -v`
Expected: 全部通过

- [ ] **Step 7: 提交**

```bash
git add app/agents/supervisor.py app/main.py tests/test_supervisor.py tests/test_api_phase2.py
git commit -m "feat: Supervisor 意图分类与路由入口"
```

### Task 11: 助手前端面板

**Files:**
- Modify: `app/web/src/api.js`（+ 助手函数）
- Create: `app/web/src/components/AgentPanel.jsx`
- Modify: `app/web/src/App.jsx`（+ 助手 Tab）

- [ ] **Step 1: 在 `app/web/src/api.js` 末尾追加助手函数**

```js
export async function sendAgentMessage(message) {
  const res = await fetch('/api/agent/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
```

- [ ] **Step 2: 创建 `app/web/src/components/AgentPanel.jsx`**

```jsx
import { useState } from 'react'
import { sendAgentMessage } from '../api.js'

export default function AgentPanel() {
  const [message, setMessage] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const handleSend = async () => {
    if (!message.trim()) return
    setBusy(true)
    try {
      setResult(await sendAgentMessage(message))
    } catch (e) {
      setResult({ intent: 'error', message: e.message, payload: {} })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          placeholder="例如：分析近期岗位趋势 / 查一下这家公司的面试流程 / 我要上传简历"
          className="w-full border rounded-lg p-3 text-sm"
        />
        <button
          onClick={handleSend}
          disabled={busy || !message.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
        >
          {busy ? '处理中…' : '发送'}
        </button>
      </div>
      {result && (
        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-sm">
            意图：<span className="font-mono text-blue-600">{result.intent}</span>
          </p>
          <p className="text-sm">{result.message}</p>
          {result.payload && Object.keys(result.payload).length > 0 && (
            <pre className="whitespace-pre-wrap text-xs bg-slate-50 rounded-lg p-3">
              {JSON.stringify(result.payload, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 修改 `app/web/src/App.jsx`（注册助手 Tab）**

```jsx
import AgentPanel from './components/AgentPanel.jsx'

const TABS = [
  { key: 'resume', label: '简历', component: ResumePanel },
  { key: 'jd', label: '岗位 JD', component: JDPanel },
  { key: 'match', label: '匹配与自荐信', component: MatchPanel },
  { key: 'pipeline', label: '投递看板', component: PipelinePanel },
  { key: 'agent', label: '助手', component: AgentPanel }
]
```

- [ ] **Step 4: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add app/web/src/api.js app/web/src/components/AgentPanel.jsx app/web/src/App.jsx
git commit -m "feat: 助手前端面板"
```

### Task 12: 匹配页「记录投递」入口

**Files:**
- Modify: `app/web/src/components/MatchPanel.jsx`

- [ ] **Step 1: 修改 `app/web/src/components/MatchPanel.jsx`**

在导入区追加 `createApplication`：

```jsx
import { createApplication, generateCoverLetter, runMatch } from '../api.js'
```

在 `handleCover` 之后追加处理函数：

```jsx
const handleApply = async (matchId) => {
  setBusyId(matchId)
  try {
    const data = await createApplication(matchId)
    setProgress(`已记录投递 application_id=${data.application_id}`)
  } catch (e) {
    setProgress(`记录投递失败：${e.message}`)
  } finally {
    setBusyId('')
  }
}
```

在结果卡片中「生成自荐信」按钮旁追加：

```jsx
<button
  onClick={() => handleApply(r.match_id)}
  disabled={busyId === r.match_id}
  className="px-3 py-1.5 bg-slate-700 text-white rounded-lg text-sm disabled:opacity-50"
>
  记录投递
</button>
```

- [ ] **Step 2: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交**

```bash
git add app/web/src/components/MatchPanel.jsx
git commit -m "feat: 匹配结果一键记录投递"
```

---

## Milestone D：工程化与验收

### Task 13: README 更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 `README.md` 功能清单**

把「功能（Phase 1）」小节替换为：

```markdown
## 功能

- 简历 PDF 解析与 LLM 结构化（人工确认后入库）
- JD 多来源录入（粘贴文本 / URL 抓取 / 批量导入）
- 四维可解释匹配打分 + 差距分析（LangGraph 工作流）
- 自荐信生成 + LLM-as-judge 自检重写
- 投递状态机（非法跳转拦截 / 跟进建议 / 提醒）
- 企业研究（网页搜索 + LLM 报告）
- 市场洞察（技能频次 / 薪资统计 / 城市与公司分布）
- Supervisor 意图识别与助手入口
- SSE 实时匹配进度
```

并在「测试」小节追加：

```markdown
环境变量补充：`SEARCH_API_KEY`（Tavily，可选；未配置时企业研究降级为纯 LLM 生成）
```

- [ ] **Step 2: 在 `.env.example` 追加搜索配置**

```bash
SEARCH_API_KEY=
SEARCH_PROVIDER=tavily
```

- [ ] **Step 3: 提交**

```bash
git add README.md .env.example
git commit -m "docs: README 与配置更新（Phase 2）"
```

### Task 14: 端到端验收清单

**Files:** 无（人工验收）

- [ ] **Step 1: 全量回归**

Run: `pytest tests/ -v`
Expected: 全部通过（Phase 1 + Phase 2 约 45 个用例）

- [ ] **Step 2: 投递闭环走查**

1. 在「匹配与自荐信」生成一条匹配 → 点击「记录投递」。
2. 进入「投递看板」→ 看到记录，状态 `applied`，等待天数 0。
3. 点击「转为 screening」→ 状态更新，历史 2 条。
4. 尝试非法跳转（如直接转 offer）→ 后端 422，前端提示。
5. 注册自定义状态 `offer_pending`（from applied, next offer）→ 可从 applied 转入。

Expected: 5 步全部符合预期。

- [ ] **Step 3: 情报走查**

1. 「岗位 JD」页粘贴两条 JD，空行分隔，点「批量录入」。
2. 点「生成洞察报告」→ 看到技能频次、薪资统计、城市/公司分布。
3. 在 JD 列表点「企业研究」→ 看到面试流程/薪资参考（未配置 SEARCH_API_KEY 时显示降级说明）。

Expected: 3 步全部可完成。

- [ ] **Step 4: 助手走查**

1. 助手页输入「分析近期岗位趋势」→ 返回 intent=market_insight 与报告。
2. 输入「帮我加一条 JD」→ 返回 jd_add 引导。

Expected: 2 步符合预期。

- [ ] **Step 5: Docker 走查**

Run: `docker compose up --build`
Expected: 容器内完成 Step 2–4 主路径。

- [ ] **Step 6: 收尾提交（如有修复）**

```bash
git add -A
git commit -m "fix: Phase 2 验收修复"
```

---

## 自检记录

### 1. Spec 覆盖

| 设计文档要求 | 对应任务 |
|------------|---------|
| 岗位情报 Agent（多源采集 + 企业研究 + 市场洞察） | Task 6、7、8、9 |
| 批量录入 JD 后可跑洞察报告 | Task 8、9 |
| 投递管理（状态机 + 提醒 + follow-up 建议） | Task 3、4、5 |
| 投递状态机非法跳转被拒绝 | Task 3、4（422） |
| 自定义状态与退回 | Task 3（register_custom_status + 回退边） |
| Supervisor（意图识别 + 路由） | Task 10、11 |
| 前端看板（投递/洞察/研究/助手） | Task 5、9、11、12 |

Phase 3（面试陪练 + 评测平台）、Phase 4（打磨交付）按设计文档后续另立计划。

### 2. 占位符扫描

已全文扫描：无 TBD / TODO / 「后续实现」等占位；所有代码步骤均含完整代码。

### 3. 类型与命名一致性

- 状态名统一小写英文：`applied / screening / interview / offer / accepted / rejected`，前后端与测试一致。
- `to_payload` 返回键（`application_id` / `current_status` / `allowed_next` / `waiting_days` / `suggestion` / `custom_statuses`）被 API 与 PipelinePanel 一致消费。
- 自定义状态注册参数统一为 `{status, from_status, next}`（service → schema → 前端一致）。
- `SearchTool` 注入约定：`search: SearchTool | None = None`，与既有 `llm` 注入风格一致。
- 报告键（`company / business_lines / interview_process / salary_reference / team_background / tips / source_note`）在 schema、research_agent、前端渲染处一致。
- 洞察报告键（`total_jds / top_skills / salary_stats / location_counts / company_counts / generated_at`）在 service、API、前端一致。
