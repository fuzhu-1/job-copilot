# Job Copilot · Phase 3（陪练与评测）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现面试陪练 Agent（按 JD + 简历定制的多轮模拟面试与 STAR 反馈）和评测模块（golden set、LLM-as-judge、回归运行、可视化报告），让系统「怎么证明自己靠谱」有据可查。

**Architecture:** 面试陪练：`InterviewSession` 表存有状态多轮会话，服务层负责「首问 → 评分/反馈 → 追问 → 满轮总结」，LLM 可注入。评测：`EvalCase`（golden set）+ `EvalRun` 表；`app/eval/` 包分三层——`golden.py`（从 JSON 文件同步用例）、`judge.py`（match 确定性区间判定 / cover_letter LLM-as-judge / interview 阈值判定）、`runner.py`（逐条执行并聚合指标）；评测结果写入 `EvalRun` 供前端展示与回归对比。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / OpenAI SDK / React 18 + Vite + Tailwind / pytest。

**前置条件:** Phase 1、Phase 2 已按对应计划完成并全部测试通过。

**项目根目录:** `job-copilot/`。所有相对路径均相对于该目录。

---

## 文件结构总览（Phase 3 新增/修改）

```
job-copilot/
├── app/
│   ├── models.py                          # 修改：+ InterviewSession、EvalCase、EvalRun
│   ├── schemas.py                         # 修改：+ 陪练/评测 schema
│   ├── eval/                              # 新增：评测包
│   │   ├── __init__.py
│   │   ├── golden.py                      # golden set JSON 同步
│   │   ├── judge.py                       # 三类判定
│   │   └── runner.py                      # 评测运行与指标聚合
│   ├── services/
│   │   └── interview_service.py           # 新增：面试陪练服务
│   ├── main.py                            # 修改：+ 陪练/评测端点
│   ├── data/golden_set.json               # 新增：golden set 样例模板
│   └── web/src/
│       ├── api.js                         # 修改：+ 陪练/评测函数
│       ├── components/
│       │   ├── InterviewPanel.jsx         # 新增：陪练会话界面
│       │   └── EvalPanel.jsx              # 新增：评测报告界面
│       └── App.jsx                        # 修改：+ 陪练/评测 Tab
└── tests/
    ├── test_interview_service.py          # 新增
    ├── test_eval_golden.py                # 新增
    ├── test_eval_runner.py                # 新增
    └── test_api_phase3.py                 # 新增：Phase 3 API 集成
```

**模块边界（Phase 3）：**
- `app/services/interview_service.py`：唯一陪练会话逻辑，输入 `(jd_id, resume_id)` 或 `(session_id, answer)`，输出结构化消息与总结；不碰 HTTP。
- `app/eval/golden.py`：只负责把 JSON 文件同步进 `EvalCase` 表（按 title 幂等）。
- `app/eval/judge.py`：纯函数判定，match/interview 不依赖 LLM，cover_letter 依赖注入的 LLM。
- `app/eval/runner.py`：编排：逐条执行 → 判定 → 聚合 metrics；不关心 HTTP 与前端。
- 陪练与评测彼此独立，可单独测试；评测 runner 复用 `match_service` / `cover_letter_service` / `interview_service`。

---

## Milestone A：面试陪练 Agent

### Task 1: InterviewSession 模型与 Schemas

**Files:**
- Modify: `app/models.py`（+ InterviewSession）
- Modify: `app/schemas.py`（+ 陪练 schema）
- Test: `tests/test_models.py`（追加用例）

- [ ] **Step 1: 在 `tests/test_models.py` 末尾追加失败测试**

```python
def test_interview_session_model(db_session):
    resume = Resume(raw_text="r", structured_json={})
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    session = InterviewSession(
        jd_id=jd.id,
        resume_id=resume.id,
        status="active",
        messages_json=[{"role": "assistant", "content": "首问", "score": None, "feedback": None}],
    )
    db_session.add(session)
    db_session.commit()
    loaded = db_session.get(InterviewSession, session.id)
    assert loaded.status == "active"
    assert loaded.messages_json[0]["content"] == "首问"
```

- [ ] **Step 2: 在 `tests/test_models.py` 顶部更新导入**

```python
from app.models import (
    Application,
    EvalCase,
    EvalRun,
    InterviewSession,
    JD,
    JDReport,
    Match,
    Resume,
)
```

（`EvalCase` / `EvalRun` 将在 Task 5 使用，先一并导入；本任务运行测试时模型尚不存在会失败，Task 5 补齐后通过。）

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 4: 在 `app/models.py` 末尾追加 InterviewSession 模型**

```python
class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    jd_id: Mapped[str] = mapped_column(ForeignKey("jds.id"))
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id"))
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    messages_json: Mapped[list] = mapped_column(JSON, default=list)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
```

- [ ] **Step 5: 在 `app/schemas.py` 末尾追加陪练 schema**

```python
class InterviewCreate(BaseModel):
    jd_id: str
    resume_id: str


class InterviewRespond(BaseModel):
    answer: str


class AnswerEvaluation(BaseModel):
    score: float = 0.0
    feedback: str = ""
    next_question: str = ""


class InterviewSummary(BaseModel):
    overall_score: float = 0.0
    strengths: list[str] = []
    weaknesses: list[str] = []
    improvement_plan: list[str] = []
```

- [ ] **Step 6: 提交（本任务允许模型导入失败时的红测试先提交，Task 2 实现后全绿）**

```bash
git add app/models.py app/schemas.py tests/test_models.py
git commit -m "feat: InterviewSession 模型与陪练 schema"
```

> 说明：若你严格执行「红→绿」节奏，可把本任务与 Task 2 合并提交；此处按文件归组提交，Task 2 完成时补跑全量测试。

### Task 2: 面试陪练服务

**Files:**
- Create: `app/services/interview_service.py`
- Test: `tests/test_interview_service.py`

- [ ] **Step 1: 写失败测试 `tests/test_interview_service.py`**

```python
import pytest

from app.models import InterviewSession, JD, Resume
from app.services.interview_service import MAX_TURNS, create_session, respond


def _setup(db_session):
    resume = Resume(
        raw_text="r",
        structured_json={"name": "张三", "skills": ["Python", "RAG"]},
        status="confirmed",
    )
    jd = JD(
        company="京东",
        title="LLM 实习生",
        raw_text="j",
        structured_json={"requirements": ["Python", "RAG"]},
    )
    db_session.add_all([resume, jd])
    db_session.commit()
    return jd, resume


class FakeLLM:
    def __init__(self):
        self.complete_calls = 0
        self.structured_calls = 0

    def complete(self, messages, max_tokens=2000):
        self.complete_calls += 1
        return "请先介绍你做过的一个 AI 项目"

    def complete_structured(self, messages, schema, max_tokens=2000):
        self.structured_calls += 1
        if schema.__name__ == "AnswerEvaluation":
            return schema.model_validate(
                {
                    "score": 85.0,
                    "feedback": "结构清晰，建议补充量化结果",
                    "next_question": "追问：你如何评估 RAG 检索质量？",
                }
            ).model_dump()
        if schema.__name__ == "InterviewSummary":
            return schema.model_validate(
                {
                    "overall_score": 82.0,
                    "strengths": ["项目讲解清晰"],
                    "weaknesses": ["缺少量化指标"],
                    "improvement_plan": ["每个项目准备 2 个量化亮点"],
                }
            ).model_dump()
        raise AssertionError(f"unexpected schema: {schema.__name__}")


def test_create_session(db_session):
    jd, resume = _setup(db_session)
    session = create_session(db_session, jd.id, resume.id, llm=FakeLLM())
    assert session.status == "active"
    assert session.messages_json[0]["role"] == "assistant"
    assert "AI 项目" in session.messages_json[0]["content"]


def test_create_session_missing_jd_raises(db_session):
    resume = Resume(raw_text="r", structured_json={}, status="confirmed")
    db_session.add(resume)
    db_session.commit()
    with pytest.raises(KeyError):
        create_session(db_session, "nope", resume.id, llm=FakeLLM())


def test_full_session_flow_completes_after_max_turns(db_session):
    jd, resume = _setup(db_session)
    llm = FakeLLM()
    session = create_session(db_session, jd.id, resume.id, llm=llm)
    last = None
    for i in range(MAX_TURNS):
        last = respond(db_session, session.id, f"回答 {i + 1}", llm=llm)
    assert last["completed"] is True
    assert last["summary"]["overall_score"] == 82.0
    loaded = db_session.get(InterviewSession, session.id)
    assert loaded.status == "completed"
    assert len(loaded.messages_json) == 1 + MAX_TURNS * 2


def test_respond_completed_session_raises(db_session):
    jd, resume = _setup(db_session)
    llm = FakeLLM()
    session = create_session(db_session, jd.id, resume.id, llm=llm)
    for _ in range(MAX_TURNS):
        respond(db_session, session.id, "回答", llm=llm)
    with pytest.raises(ValueError):
        respond(db_session, session.id, "再来一轮", llm=llm)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_interview_service.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.interview_service`）

- [ ] **Step 3: 创建 `app/services/interview_service.py`**

```python
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import InterviewSession, JD, Resume
from app.schemas import AnswerEvaluation, InterviewSummary

MAX_TURNS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summary(jd: JD, resume: Resume) -> str:
    return (
        f"JD：{json.dumps(jd.structured_json, ensure_ascii=False)}\n"
        f"简历：{json.dumps(resume.structured_json, ensure_ascii=False)}"
    )[:8000]


def create_session(
    db: Session, jd_id: str, resume_id: str, llm: LLMService | None = None
) -> InterviewSession:
    llm = llm or LLMService()
    jd = db.get(JD, jd_id)
    resume = db.get(Resume, resume_id)
    if jd is None:
        raise KeyError(f"jd not found: {jd_id}")
    if resume is None:
        raise KeyError(f"resume not found: {resume_id}")
    first_question = llm.complete(
        [
            {
                "role": "system",
                "content": "你是资深面试官。基于岗位 JD 与候选人简历，生成第一个面试问题。"
                "问题要贴合岗位要求，并尽量结合候选人项目经历。只输出问题本身。",
            },
            {"role": "user", "content": _summary(jd, resume)},
        ]
    )
    session = InterviewSession(
        jd_id=jd_id,
        resume_id=resume_id,
        status="active",
        messages_json=[
            {"role": "assistant", "content": first_question, "score": None, "feedback": None}
        ],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def respond(
    db: Session, session_id: str, answer: str, llm: LLMService | None = None
) -> dict:
    llm = llm or LLMService()
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise KeyError(f"interview session not found: {session_id}")
    if session.status != "active":
        raise ValueError("面试会话已结束")

    messages = list(session.messages_json)
    messages.append({"role": "user", "content": answer, "score": None, "feedback": None})
    jd = db.get(JD, session.jd_id)
    resume = db.get(Resume, session.resume_id)
    last_question = next(
        m["content"] for m in reversed(messages) if m["role"] == "assistant"
    )
    evaluation = llm.complete_structured(
        [
            {
                "role": "system",
                "content": "你是面试评分官。根据面试问题与候选人回答评分并给出 STAR 反馈，然后生成追问或下一题。"
                "输出 JSON：score(0-100)、feedback(结构/内容/量化建议)、next_question(追问或下一题)。",
            },
            {
                "role": "user",
                "content": (
                    f"{_summary(jd, resume)}\n"
                    f"面试问题：{last_question}\n候选人回答：{answer}"
                ),
            },
        ],
        AnswerEvaluation,
    )
    score = float(evaluation["score"])
    feedback = evaluation["feedback"]
    next_question = evaluation["next_question"]

    assistant_turns = [m for m in messages if m["role"] == "assistant"]
    completed = len(assistant_turns) >= MAX_TURNS
    closing = "（面试结束，正在生成总结）" if completed else next_question
    messages.append(
        {"role": "assistant", "content": closing, "score": score, "feedback": feedback}
    )
    session.messages_json = messages
    session.updated_at = _now()

    result = {
        "score": score,
        "feedback": feedback,
        "next_question": next_question,
        "completed": completed,
        "summary": None,
    }
    if completed:
        session.status = "completed"
        summary = _summarize(session, jd, resume, llm)
        session.summary_json = summary
        result["summary"] = summary

    db.commit()
    db.refresh(session)
    return result


def _summarize(session: InterviewSession, jd: JD, resume: Resume, llm: LLMService) -> dict:
    transcript = json.dumps(session.messages_json, ensure_ascii=False)[:12000]
    return llm.complete_structured(
        [
            {
                "role": "system",
                "content": "你是面试复盘教练。基于完整对话生成总结，输出 JSON："
                "overall_score(0-100)、strengths、weaknesses、improvement_plan。",
            },
            {"role": "user", "content": f"{_summary(jd, resume)}\n对话记录：\n{transcript}"},
        ],
        InterviewSummary,
    )


def get_session_payload(session: InterviewSession) -> dict:
    return {
        "session_id": session.id,
        "jd_id": session.jd_id,
        "resume_id": session.resume_id,
        "status": session.status,
        "messages": session.messages_json,
        "summary": session.summary_json,
        "created_at": session.created_at.isoformat(),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_interview_service.py tests/test_models.py -v`
Expected: 全部通过（陪练 4 个 + 模型 5 个）

- [ ] **Step 5: 提交**

```bash
git add app/services/interview_service.py tests/test_interview_service.py
git commit -m "feat: 面试陪练服务（提问/评分/追问/总结）"
```

### Task 3: 陪练 API 端点

**Files:**
- Modify: `app/main.py`（+ 陪练端点与导入）
- Test: `tests/test_api_phase3.py`（本任务先写陪练用例）

- [ ] **Step 1: 写失败测试 `tests/test_api_phase3.py`（本任务先写陪练用例，评测用例后续任务追加）**

```python
from app.models import JD, Resume


def _setup(client, db_session):
    resume = Resume(
        raw_text="r",
        structured_json={"name": "张三", "skills": ["Python", "RAG"]},
        status="confirmed",
    )
    jd = JD(
        company="京东",
        title="LLM 实习生",
        raw_text="j",
        structured_json={"requirements": ["Python", "RAG"]},
    )
    db_session.add_all([resume, jd])
    db_session.commit()
    return jd.id, resume.id


def test_interview_flow(client, db_session, monkeypatch):
    import app.main as main_module

    class FakeLLM:
        def complete(self, messages, max_tokens=2000):
            return "请介绍一个你做过的大模型项目"

        def complete_structured(self, messages, schema, max_tokens=2000):
            if schema.__name__ == "AnswerEvaluation":
                return schema.model_validate(
                    {
                        "score": 85.0,
                        "feedback": "结构清晰",
                        "next_question": "追问：项目里最难的点是什么？",
                    }
                ).model_dump()
            if schema.__name__ == "InterviewSummary":
                return schema.model_validate(
                    {
                        "overall_score": 82.0,
                        "strengths": ["清晰"],
                        "weaknesses": ["少量化"],
                        "improvement_plan": ["补充量化"],
                    }
                ).model_dump()
            raise AssertionError(schema.__name__)

    monkeypatch.setattr(main_module, "llm", FakeLLM())
    jd_id, resume_id = _setup(client, db_session)
    res = client.post("/api/interviews/sessions", json={"jd_id": jd_id, "resume_id": resume_id})
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    assert res.json()["messages"][0]["role"] == "assistant"

    res2 = client.post(
        f"/api/interviews/sessions/{session_id}/respond",
        json={"answer": "我做过 RAG 检索优化"},
    )
    assert res2.status_code == 200
    assert res2.json()["score"] == 85.0
    assert res2.json()["completed"] is False

    res3 = client.get(f"/api/interviews/sessions/{session_id}")
    assert res3.status_code == 200
    assert len(res3.json()["messages"]) == 3


def test_interview_missing_jd_404(client):
    res = client.post(
        "/api/interviews/sessions",
        json={"jd_id": "nope", "resume_id": "nope"},
    )
    assert res.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api_phase3.py -v`
Expected: FAIL（404，端点不存在）

- [ ] **Step 3: 修改 `app/main.py`**

在导入区追加：

```python
from app.schemas import InterviewCreate, InterviewRespond
from app.services import interview_service
from app.models import InterviewSession
```

（若 `from app.models import ...` 已存在其他导入，合并即可。）

在投递端点之后追加陪练端点：

```python
@app.post("/api/interviews/sessions")
def create_interview(payload: InterviewCreate, db: Session = Depends(get_session)):
    try:
        session = interview_service.create_session(db, payload.jd_id, payload.resume_id, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return interview_service.get_session_payload(session)


@app.post("/api/interviews/sessions/{session_id}/respond")
def respond_interview(
    session_id: str, payload: InterviewRespond, db: Session = Depends(get_session)
):
    try:
        return interview_service.respond(db, session_id, payload.answer, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/interviews/sessions/{session_id}")
def get_interview(session_id: str, db: Session = Depends(get_session)):
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return interview_service.get_session_payload(session)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_api_phase3.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add app/main.py tests/test_api_phase3.py
git commit -m "feat: 面试陪练 API 端点"
```

### Task 4: 陪练前端

**Files:**
- Modify: `app/web/src/api.js`（+ 陪练函数）
- Create: `app/web/src/components/InterviewPanel.jsx`
- Modify: `app/web/src/App.jsx`（+ 陪练 Tab）

- [ ] **Step 1: 在 `app/web/src/api.js` 末尾追加陪练函数**

```js
export async function createInterviewSession(jdId, resumeId) {
  const res = await fetch('/api/interviews/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd_id: jdId, resume_id: resumeId })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function respondInterview(sessionId, answer) {
  const res = await fetch(`/api/interviews/sessions/${sessionId}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function getInterviewSession(sessionId) {
  const res = await fetch(`/api/interviews/sessions/${sessionId}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
```

- [ ] **Step 2: 创建 `app/web/src/components/InterviewPanel.jsx`**

```jsx
import { useEffect, useState } from 'react'
import {
  createInterviewSession,
  getInterviewSession,
  listJDs,
  respondInterview
} from '../api.js'

export default function InterviewPanel({ resumeId }) {
  const [jds, setJds] = useState([])
  const [jdId, setJdId] = useState('')
  const [session, setSession] = useState(null)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    listJDs().then((d) => {
      setJds(d.jds)
      if (d.jds.length > 0) setJdId(d.jds[0].jd_id)
    }).catch((e) => setMessage(`加载 JD 列表失败：${e.message}`))
  }, [])

  const handleStart = async () => {
    if (!jdId || !resumeId) {
      setMessage('请先确认简历并至少录入一条 JD')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      const data = await createInterviewSession(jdId, resumeId)
      setSession(data)
      setAnswer('')
    } catch (e) {
      setMessage(`开始失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleRespond = async () => {
    if (!answer.trim() || !session) return
    setBusy(true)
    try {
      const result = await respondInterview(session.session_id, answer)
      const updated = await getInterviewSession(session.session_id)
      setSession(updated)
      setAnswer('')
      if (result.completed) setMessage('面试完成，已生成总结')
    } catch (e) {
      setMessage(`回答提交失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {!session ? (
        <div className="bg-white border rounded-lg p-4 space-y-3">
          <div className="text-sm">当前简历：<span className="font-mono">{resumeId || '（未确认）'}</span></div>
          <select value={jdId} onChange={(e) => setJdId(e.target.value)} className="w-full border rounded-lg p-2 text-sm">
            {jds.map((jd) => (
              <option key={jd.jd_id} value={jd.jd_id}>{jd.company} · {jd.title}</option>
            ))}
          </select>
          <button onClick={handleStart} disabled={busy} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
            {busy ? '创建中…' : '开始模拟面试'}
          </button>
          {message && <p className="text-sm text-slate-600">{message}</p>}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex justify-between text-xs text-slate-500">
              <span>会话：{session.session_id}</span>
              <span>状态：{session.status}</span>
            </div>
            {session.messages.map((m, i) => (
              <div key={i} className={`rounded-lg p-3 text-sm ${m.role === 'assistant' ? 'bg-blue-50' : 'bg-slate-50'}`}>
                <div className="font-semibold mb-1">{m.role === 'assistant' ? '面试官' : '我'}</div>
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.feedback && (
                  <div className="mt-2 text-xs text-slate-600">
                    评分：{m.score} · 反馈：{m.feedback}
                  </div>
                )}
              </div>
            ))}
          </div>
          {session.status === 'active' && (
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={4}
                placeholder="输入你的回答…"
                className="w-full border rounded-lg p-3 text-sm"
              />
              <button onClick={handleRespond} disabled={busy || !answer.trim()} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
                {busy ? '提交中…' : '提交回答'}
              </button>
              {message && <p className="text-sm text-slate-600">{message}</p>}
            </div>
          )}
          {session.summary && Object.keys(session.summary).length > 0 && (
            <div className="bg-white border rounded-lg p-4 space-y-2">
              <h2 className="text-sm font-semibold">面试总结 · 总分 {session.summary.overall_score}</h2>
              <p className="text-sm">优势：{session.summary.strengths.join('、')}</p>
              <p className="text-sm">不足：{session.summary.weaknesses.join('、')}</p>
              <p className="text-sm">改进计划：{session.summary.improvement_plan.join('；')}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 修改 `app/web/src/App.jsx`（注册陪练 Tab）**

```jsx
import InterviewPanel from './components/InterviewPanel.jsx'

const TABS = [
  { key: 'resume', label: '简历', component: ResumePanel },
  { key: 'jd', label: '岗位 JD', component: JDPanel },
  { key: 'match', label: '匹配与自荐信', component: MatchPanel },
  { key: 'pipeline', label: '投递看板', component: PipelinePanel },
  { key: 'interview', label: '面试陪练', component: InterviewPanel },
  { key: 'agent', label: '助手', component: AgentPanel }
]
```

- [ ] **Step 4: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add app/web/src/api.js app/web/src/components/InterviewPanel.jsx app/web/src/App.jsx
git commit -m "feat: 面试陪练前端"
```

---

## Milestone B：评测模块

### Task 5: 评测模型与 golden set 同步

**Files:**
- Modify: `app/models.py`（+ EvalCase、EvalRun）
- Create: `app/eval/__init__.py`
- Create: `app/eval/golden.py`
- Create: `data/golden_set.json`
- Test: `tests/test_eval_golden.py`

- [ ] **Step 1: 在 `app/models.py` 末尾追加评测模型**

```python
class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), default="")
    task_type: Mapped[str] = mapped_column(String(30))  # match | cover_letter | interview
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 2: 创建 `app/eval/__init__.py`（空文件）与 `app/eval/golden.py`**

```python
import json

from sqlalchemy.orm import Session

from app.models import EvalCase


def sync_golden_set(db: Session, path: str) -> dict:
    """从 JSON 文件同步 golden set 到 EvalCase 表（按 title 幂等 upsert）。"""
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    existing = {c.title: c for c in db.query(EvalCase).all()}
    added = 0
    updated = 0
    for item in cases:
        case = existing.get(item["title"])
        if case is None:
            db.add(
                EvalCase(
                    title=item["title"],
                    task_type=item["task_type"],
                    input_json=item["input"],
                    expected_json=item["expected"],
                )
            )
            added += 1
        else:
            case.task_type = item["task_type"]
            case.input_json = item["input"]
            case.expected_json = item["expected"]
            updated += 1
    db.commit()
    return {"added": added, "updated": updated, "total": len(cases)}
```

- [ ] **Step 3: 创建 `data/golden_set.json`（样例模板，ID 需替换为真实数据）**

```json
[
  {
    "title": "match-example",
    "task_type": "match",
    "input": {"resume_id": "RESUME_ID", "jd_id": "JD_ID"},
    "expected": {"total_min": 70, "total_max": 95, "gaps": []}
  },
  {
    "title": "cover-letter-example",
    "task_type": "cover_letter",
    "input": {"match_id": "MATCH_ID"},
    "expected": {"keywords": ["Python"], "min_score": 0.8}
  },
  {
    "title": "interview-example",
    "task_type": "interview",
    "input": {"session_id": "SESSION_ID"},
    "expected": {"min_score": 60}
  }
]
```

- [ ] **Step 4: 写失败测试 `tests/test_eval_golden.py`**

```python
import json

from app.eval.golden import sync_golden_set
from app.models import EvalCase


def test_sync_golden_set_idempotent(db_session, tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(
        json.dumps(
            [
                {
                    "title": "case-1",
                    "task_type": "match",
                    "input": {"resume_id": "r1", "jd_id": "j1"},
                    "expected": {"total_min": 70, "total_max": 95},
                },
                {
                    "title": "case-1",
                    "task_type": "match",
                    "input": {"resume_id": "r1", "jd_id": "j1"},
                    "expected": {"total_min": 75, "total_max": 95},
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    first = sync_golden_set(db_session, str(path))
    assert first["added"] == 1
    assert first["updated"] == 1
    assert db_session.query(EvalCase).count() == 1
    case = db_session.query(EvalCase).one()
    assert case.expected_json["total_min"] == 75


def test_sync_golden_set_empty_file(db_session, tmp_path):
    path = tmp_path / "golden.json"
    path.write_text("[]", encoding="utf-8")
    result = sync_golden_set(db_session, str(path))
    assert result == {"added": 0, "updated": 0, "total": 0}
```

- [ ] **Step 5: 运行测试确认通过（含模型回归）**

Run: `pytest tests/test_eval_golden.py tests/test_models.py -v`
Expected: 全部通过（评测 2 个 + 模型 6 个）

- [ ] **Step 6: 提交**

```bash
git add app/models.py app/eval data/golden_set.json tests/test_eval_golden.py
git commit -m "feat: 评测模型与 golden set 同步"
```

### Task 6: 评测判定器（judge）

**Files:**
- Create: `app/eval/judge.py`
- Test: `tests/test_eval_runner.py`（本任务先写 judge 用例）

- [ ] **Step 1: 写失败测试（`tests/test_eval_runner.py`，本任务先含 judge 用例，Task 7 追加 runner 用例）**

```python
from app.eval.judge import judge_cover_letter, judge_interview, judge_match
from app.schemas import DimensionScores, MatchResult


def test_judge_match_range():
    result = MatchResult(
        match_id="m",
        jd_id="j",
        dimension_scores=DimensionScores(),
        total_score=80.0,
    )
    assert judge_match(result, {"total_min": 70, "total_max": 95})["passed"] is True
    assert judge_match(result, {"total_min": 90, "total_max": 95})["passed"] is False


def test_judge_match_gaps():
    result = MatchResult(
        match_id="m",
        jd_id="j",
        dimension_scores=DimensionScores(),
        total_score=80.0,
        gaps=["缺少企业级项目经验"],
    )
    assert (
        judge_match(result, {"total_min": 0, "total_max": 100, "gaps": ["缺少企业级项目经验"]})[
            "passed"
        ]
        is True
    )
    assert (
        judge_match(result, {"total_min": 0, "total_max": 100, "gaps": ["其他差距"]})["passed"]
        is False
    )


def test_judge_interview():
    assert judge_interview({"overall_score": 82.0}, {"min_score": 80})["passed"] is True
    assert judge_interview({"overall_score": 60.0}, {"min_score": 80})["passed"] is False


def test_judge_cover_letter():
    class FakeLLM:
        def complete_structured(self, messages, schema, max_tokens=2000):
            return schema.model_validate({"score": 0.9, "feedback": "ok"}).model_dump()

    result = judge_cover_letter(
        "熟悉 Python 与 LangGraph", {"keywords": ["Python"], "min_score": 0.8}, FakeLLM()
    )
    assert result["passed"] is True

    missing = judge_cover_letter(
        "熟悉 Python", {"keywords": ["RAG"], "min_score": 0.8}, FakeLLM()
    )
    assert missing["passed"] is False
    assert missing["missing_keywords"] == ["RAG"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_eval_runner.py -v`
Expected: FAIL（`ModuleNotFoundError: app.eval.judge`）

- [ ] **Step 3: 创建 `app/eval/judge.py`**

```python
from app.schemas import MatchResult
from app.services.cover_letter_service import JudgeScore


def judge_match(result: MatchResult, expected: dict) -> dict:
    """确定性判定：总分在期望区间内，且差距均被期望覆盖。"""
    lo = expected.get("total_min", 0)
    hi = expected.get("total_max", 100)
    total = result.total_score
    in_range = lo <= total <= hi
    expected_gaps = expected.get("gaps", [])
    gaps_ok = True
    if expected_gaps:
        gaps_ok = all(any(g in exp for exp in expected_gaps) for g in result.gaps)
    return {
        "task_type": "match",
        "score": total,
        "passed": in_range and gaps_ok,
        "detail": f"total={total}, range=[{lo},{hi}], gaps_ok={gaps_ok}",
    }


def judge_interview(summary: dict, expected: dict) -> dict:
    """确定性判定：总结总分不低于阈值。"""
    overall = float(summary.get("overall_score", 0))
    min_score = expected.get("min_score", 60)
    return {
        "task_type": "interview",
        "score": overall,
        "passed": overall >= min_score,
        "detail": f"overall={overall}, min={min_score}",
    }


def judge_cover_letter(content: str, expected: dict, llm) -> dict:
    """LLM-as-judge：rubric 打分 + 关键词覆盖。"""
    keywords = expected.get("keywords", [])
    missing = [k for k in keywords if k not in content]
    min_score = expected.get("min_score", 0.8)
    prompt = (
        "你是自荐信评审。按 rubric 打分（0-1 分，保留两位小数）：\n"
        "1) 覆盖 JD 关键要求 2) 有量化成果 3) 结构完整 4) 语言得体\n"
        f"自荐信：\n{content[:4000]}\n"
        '输出 JSON：{"score": 0.0-1.0, "feedback": "改进建议"}'
    )
    data = llm.complete_structured([{"role": "user", "content": prompt}], JudgeScore)
    score = float(data["score"])
    return {
        "task_type": "cover_letter",
        "score": round(score, 2),
        "passed": score >= min_score and not missing,
        "missing_keywords": missing,
        "detail": f"judge={score:.2f}, min={min_score}",
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_eval_runner.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add app/eval/judge.py tests/test_eval_runner.py
git commit -m "feat: 评测判定器（match/interview/cover_letter）"
```

### Task 7: 评测 runner 与 API 端点

**Files:**
- Create: `app/eval/runner.py`
- Modify: `app/main.py`（+ 评测端点）
- Test: `tests/test_eval_runner.py`（追加 runner 用例）
- Test: `tests/test_api_phase3.py`（追加评测用例）

- [ ] **Step 1: 在 `tests/test_eval_runner.py` 末尾追加 runner 用例**

```python
from app.eval.runner import run_eval
from app.models import EvalCase, JD, Match, Resume


class FakeRunLLM:
    def complete(self, messages, max_tokens=2000):
        return "自荐信草稿，熟悉 Python。"

    def complete_structured(self, messages, schema, max_tokens=2000):
        name = schema.__name__
        if name == "JudgeScore":
            return schema.model_validate({"score": 0.9, "feedback": "ok"}).model_dump()
        if name == "MatchScoring":
            return schema.model_validate(
                {
                    "skill_match": 90.0,
                    "experience_match": 80.0,
                    "education_match": 70.0,
                    "hard_requirements": 85.0,
                    "reasons": {},
                    "gaps": [],
                    "summary": "ok",
                }
            ).model_dump()
        raise AssertionError(f"unexpected schema: {name}")


def test_run_eval_metrics(db_session, vector_store):
    resume = Resume(raw_text="r", structured_json={"skills": ["Python"]}, status="confirmed")
    jd = JD(
        company="京东",
        title="实习生",
        raw_text="j",
        structured_json={"requirements": ["Python"]},
    )
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=83.0)
    db_session.add(match)
    db_session.commit()
    db_session.add_all(
        [
            EvalCase(
                title="match-ok",
                task_type="match",
                input_json={"resume_id": resume.id, "jd_id": jd.id},
                expected_json={"total_min": 70, "total_max": 95},
            ),
            EvalCase(
                title="cover-letter-ok",
                task_type="cover_letter",
                input_json={"match_id": match.id},
                expected_json={"keywords": ["Python"], "min_score": 0.8},
            ),
        ]
    )
    db_session.commit()

    report = run_eval(db_session, llm=FakeRunLLM(), vector_store=vector_store)
    metrics = report["metrics"]
    assert metrics["total_cases"] == 2
    assert metrics["passed_cases"] == 2
    assert metrics["pass_rate"] == 1.0
    assert metrics["by_type"]["match"]["avg_score"] == 83.0
    assert metrics["by_type"]["cover_letter"]["avg_score"] == 0.9


def test_run_eval_empty_golden(db_session):
    report = run_eval(db_session, llm=FakeRunLLM())
    assert report["metrics"]["total_cases"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_eval_runner.py -v`
Expected: FAIL（`ModuleNotFoundError: app.eval.runner`）

- [ ] **Step 3: 创建 `app/eval/runner.py`**

```python
from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import EvalCase, InterviewSession, Match
from app.services import cover_letter_service, match_service
from app.eval.judge import judge_cover_letter, judge_interview, judge_match
from app.vector_store import VectorStore


def run_eval(
    db: Session,
    llm: LLMService | None = None,
    vector_store: VectorStore | None = None,
) -> dict:
    """逐条执行 golden set 并聚合指标。单条失败不中断整体。"""
    llm = llm or LLMService()
    cases = db.query(EvalCase).all()
    results = []
    for case in cases:
        try:
            result = _run_case(db, case, llm, vector_store)
        except Exception as exc:
            result = {
                "task_type": case.task_type,
                "score": 0.0,
                "passed": False,
                "detail": f"error: {exc}",
            }
        results.append({"title": case.title, **result})

    by_type: dict[str, dict] = {}
    for r in results:
        bucket = by_type.setdefault(r["task_type"], {"passed": 0, "total": 0, "scores": []})
        bucket["total"] += 1
        bucket["passed"] += 1 if r["passed"] else 0
        bucket["scores"].append(r["score"])
    passed = sum(1 for r in results if r["passed"])
    metrics = {
        "total_cases": len(results),
        "passed_cases": passed,
        "pass_rate": round(passed / len(results), 2) if results else 0.0,
        "by_type": {
            t: {
                "passed": v["passed"],
                "total": v["total"],
                "avg_score": round(sum(v["scores"]) / len(v["scores"]), 2)
                if v["scores"]
                else 0.0,
            }
            for t, v in by_type.items()
        },
    }
    return {"metrics": metrics, "results": results}


def _run_case(db: Session, case: EvalCase, llm: LLMService, vector_store: VectorStore | None) -> dict:
    task_type = case.task_type
    if task_type == "match":
        result = match_service.run_match(
            db,
            case.input_json["resume_id"],
            case.input_json["jd_id"],
            vector_store or VectorStore(),
            llm=llm,
        )
        return judge_match(result, case.expected_json)
    if task_type == "cover_letter":
        match_id = case.input_json["match_id"]
        content = cover_letter_service.generate_cover_letter(
            db, match_id, "standard", llm=llm
        )["content"]
        return judge_cover_letter(content, case.expected_json, llm)
    if task_type == "interview":
        session = db.get(InterviewSession, case.input_json["session_id"])
        if session is None:
            raise KeyError("interview session not found")
        return judge_interview(session.summary_json, case.expected_json)
    raise ValueError(f"unknown task_type: {task_type}")
```

- [ ] **Step 4: 修改 `app/main.py`（+ 评测端点）**

在导入区追加：

```python
from fastapi import Body
from app.eval.golden import sync_golden_set
from app.eval.runner import run_eval
from app.models import EvalRun
```

在陪练端点之后追加评测端点：

```python
@app.post("/api/eval/golden/sync")
def golden_sync(payload: dict = Body(default={}), db: Session = Depends(get_session)):
    from pathlib import Path as _Path

    default_path = _Path(settings.upload_dir).parent / "golden_set.json"
    path = payload.get("path", str(default_path))
    return sync_golden_set(db, path)


@app.post("/api/eval/runs")
def create_eval_run(db: Session = Depends(get_session)):
    report = run_eval(db, llm=llm, vector_store=vector_store)
    run = EvalRun(status="completed", metrics_json=report["metrics"], report_json=report)
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"run_id": run.id, **report}


@app.get("/api/eval/runs")
def list_eval_runs(db: Session = Depends(get_session)):
    runs = db.query(EvalRun).order_by(EvalRun.created_at.desc()).limit(20).all()
    return {
        "runs": [
            {
                "run_id": run.id,
                "metrics": run.metrics_json,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ]
    }
```

- [ ] **Step 5: 在 `tests/test_api_phase3.py` 末尾追加评测用例**

```python
import json

from app.models import EvalCase


def test_eval_run_empty(client):
    res = client.post("/api/eval/runs")
    assert res.status_code == 200
    assert res.json()["metrics"]["total_cases"] == 0


def test_eval_runs_list(client, db_session):
    res = client.get("/api/eval/runs")
    assert res.status_code == 200
    assert "runs" in res.json()


def test_golden_sync_endpoint(client, db_session, tmp_path):
    path = tmp_path / "g.json"
    path.write_text(
        json.dumps(
            [{"title": "t1", "task_type": "match", "input": {}, "expected": {}}]
        ),
        encoding="utf-8",
    )
    res = client.post("/api/eval/golden/sync", json={"path": str(path)})
    assert res.status_code == 200
    assert res.json()["added"] == 1


def test_eval_run_with_match_case(client, db_session, monkeypatch):
    import app.main as main_module
    from app.models import JD, Match, Resume

    resume = Resume(
        raw_text="r", structured_json={"skills": ["Python"]}, status="confirmed"
    )
    jd = JD(
        company="京东",
        title="实习生",
        raw_text="j",
        structured_json={"requirements": ["Python"]},
    )
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=83.0)
    db_session.add(match)
    db_session.commit()
    db_session.add(
        EvalCase(
            title="match-ok",
            task_type="match",
            input_json={"resume_id": resume.id, "jd_id": jd.id},
            expected_json={"total_min": 70, "total_max": 95},
        )
    )
    db_session.commit()

    class FakeLLM:
        def complete_structured(self, messages, schema, max_tokens=2000):
            if schema.__name__ == "MatchScoring":
                return schema.model_validate(
                    {
                        "skill_match": 90.0,
                        "experience_match": 80.0,
                        "education_match": 70.0,
                        "hard_requirements": 85.0,
                        "reasons": {},
                        "gaps": [],
                        "summary": "ok",
                    }
                ).model_dump()
            raise AssertionError(schema.__name__)

    monkeypatch.setattr(main_module, "llm", FakeLLM())
    res = client.post("/api/eval/runs")
    assert res.status_code == 200
    assert res.json()["metrics"]["passed_cases"] == 1
    assert res.json()["metrics"]["pass_rate"] == 1.0
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/test_eval_runner.py tests/test_api_phase3.py -v`
Expected: 全部通过

- [ ] **Step 7: 提交**

```bash
git add app/eval/runner.py app/main.py tests/test_eval_runner.py tests/test_api_phase3.py
git commit -m "feat: 评测 runner 与 API 端点"
```

### Task 8: 评测前端

**Files:**
- Modify: `app/web/src/api.js`（+ 评测函数）
- Create: `app/web/src/components/EvalPanel.jsx`
- Modify: `app/web/src/App.jsx`（+ 评测 Tab）

- [ ] **Step 1: 在 `app/web/src/api.js` 末尾追加评测函数**

```js
export async function runEval() {
  const res = await fetch('/api/eval/runs', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listEvalRuns() {
  const res = await fetch('/api/eval/runs')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function syncGoldenSet(path = '') {
  const res = await fetch('/api/eval/golden/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(path ? { path } : {})
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
```

- [ ] **Step 2: 创建 `app/web/src/components/EvalPanel.jsx`**

```jsx
import { useEffect, useState } from 'react'
import { listEvalRuns, runEval, syncGoldenSet } from '../api.js'

export default function EvalPanel() {
  const [runs, setRuns] = useState([])
  const [latest, setLatest] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const refresh = async () => {
    const data = await listEvalRuns()
    setRuns(data.runs)
    if (data.runs.length > 0) setLatest(data.runs[0])
  }

  useEffect(() => {
    refresh().catch((e) => setMessage(`加载评测记录失败：${e.message}`))
  }, [])

  const handleRun = async () => {
    setBusy(true)
    setMessage('')
    try {
      const data = await runEval()
      await refresh()
      setMessage(`评测完成：通过 ${data.metrics.passed_cases}/${data.metrics.total_cases}`)
    } catch (e) {
      setMessage(`评测失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleSync = async () => {
    setBusy(true)
    try {
      const data = await syncGoldenSet()
      setMessage(`golden set 同步完成：新增 ${data.added}，更新 ${data.updated}`)
    } catch (e) {
      setMessage(`同步失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <button onClick={handleRun} disabled={busy} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
            {busy ? '评测中…' : '运行评测'}
          </button>
          <button onClick={handleSync} disabled={busy} className="px-4 py-2 bg-slate-700 text-white rounded-lg disabled:opacity-50">
            同步 golden set
          </button>
        </div>
        {message && <p className="text-sm text-slate-600">{message}</p>}
      </div>

      {latest && (
        <div className="bg-white border rounded-lg p-4 space-y-3">
          <h2 className="text-sm font-semibold">最近一次评测 · {latest.created_at.slice(0, 19).replace('T', ' ')}</h2>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-slate-50 rounded p-3">
              <div className="text-2xl font-bold text-blue-600">{latest.metrics.pass_rate * 100}%</div>
              <div className="text-xs text-slate-500">通过率</div>
            </div>
            <div className="bg-slate-50 rounded p-3">
              <div className="text-2xl font-bold">{latest.metrics.passed_cases}/{latest.metrics.total_cases}</div>
              <div className="text-xs text-slate-500">通过/总数</div>
            </div>
            <div className="bg-slate-50 rounded p-3">
              <div className="text-2xl font-bold">{Object.keys(latest.metrics.by_type).length}</div>
              <div className="text-xs text-slate-500">任务类型</div>
            </div>
          </div>
          {Object.entries(latest.metrics.by_type).map(([type, v]) => (
            <div key={type} className="flex justify-between text-sm">
              <span>{type}：{v.passed}/{v.total}</span>
              <span className="text-slate-500">平均分 {v.avg_score}</span>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white border rounded-lg p-4 space-y-2">
        <h2 className="text-sm font-semibold">历史评测（{runs.length}）</h2>
        {runs.length === 0 && <p className="text-xs text-slate-500">暂无评测记录</p>}
        {runs.map((r) => (
          <div key={r.run_id} className="flex justify-between text-xs text-slate-600 border-t pt-2">
            <span className="font-mono">{r.run_id}</span>
            <span>{r.created_at.slice(0, 19).replace('T', ' ')} · 通过率 {(r.metrics.pass_rate * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 修改 `app/web/src/App.jsx`（注册评测 Tab）**

```jsx
import EvalPanel from './components/EvalPanel.jsx'

const TABS = [
  { key: 'resume', label: '简历', component: ResumePanel },
  { key: 'jd', label: '岗位 JD', component: JDPanel },
  { key: 'match', label: '匹配与自荐信', component: MatchPanel },
  { key: 'pipeline', label: '投递看板', component: PipelinePanel },
  { key: 'interview', label: '面试陪练', component: InterviewPanel },
  { key: 'eval', label: '评测报告', component: EvalPanel },
  { key: 'agent', label: '助手', component: AgentPanel }
]
```

- [ ] **Step 4: 构建验证**

Run: `cd app/web && npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add app/web/src/api.js app/web/src/components/EvalPanel.jsx app/web/src/App.jsx
git commit -m "feat: 评测报告前端"
```

---

## Milestone C：工程化与验收

### Task 9: README 更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新 `README.md` 功能清单**

在「功能」清单追加：

```markdown
- 面试陪练（按 JD + 简历定制的多轮模拟面试与 STAR 反馈）
- 评测平台（golden set / LLM-as-judge / 回归通过率 / 可视化报告）
```

并新增「评测」小节：

```markdown
## 评测

1. 准备 golden set：编辑 `data/golden_set.json`（把示例 ID 替换为真实 resume/jd/match/session ID）。
2. 同步用例：`POST /api/eval/golden/sync`（或前端「评测报告」页点「同步 golden set」）。
3. 运行评测：`POST /api/eval/runs`（或前端点「运行评测」）。
4. 看报告：前端「评测报告」页展示通过率、分类型平均分与历史趋势。

评测基线记录在 `docs/eval-baseline.md`（Phase 4 固化）。
```

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: README 更新（Phase 3）"
```

### Task 10: 端到端验收清单

**Files:** 无（人工验收）

- [ ] **Step 1: 全量回归**

Run: `pytest tests/ -v`
Expected: 全部通过（Phase 1–3 约 60 个用例）

- [ ] **Step 2: 陪练闭环走查**

1. 「面试陪练」页选择一条 JD → 开始模拟面试 → 收到首问。
2. 连续回答 5 轮 → 每轮看到评分与 STAR 反馈。
3. 第 5 轮后会话完成，出现总结（总分/优势/不足/改进计划）。
4. 已结束会话再提交回答 → 422。

Expected: 4 步全部符合预期。

- [ ] **Step 3: 评测闭环走查**

1. 把真实数据 ID 填入 `data/golden_set.json` → 前端「评测报告」页同步。
2. 点「运行评测」→ 看到通过率、分类型平均分。
3. 修改一处匹配逻辑后重跑 → 通过率变化在报告中可见（回归价值）。

Expected: 3 步全部可完成。

- [ ] **Step 4: Docker 走查**

Run: `docker compose up --build`
Expected: 容器内完成 Step 2–3 主路径。

- [ ] **Step 5: 收尾提交（如有修复）**

```bash
git add -A
git commit -m "fix: Phase 3 验收修复"
```

---

## 自检记录

### 1. Spec 覆盖

| 设计文档要求 | 对应任务 |
|------------|---------|
| 面试陪练 Agent（有状态多轮会话） | Task 1、2、3、4 |
| STAR 结构反馈 | Task 2（AnswerEvaluation feedback 提示词） |
| 按 JD + 简历定制提问 | Task 2（_summary 注入 JD 与简历） |
| 会话持久化 | Task 1（messages_json / summary_json） |
| 评测 golden set（人工标注基准） | Task 5（EvalCase + expected_json） |
| LLM-as-judge | Task 6（judge_cover_letter） |
| 回归测试（改动前跑 golden set） | Task 7（run_eval 聚合 pass_rate） |
| 可视化报告 | Task 8（EvalPanel） |
| 人工抽样复核校准 judge | 设计文档 Phase 4 落地（docs/INTERVIEW_PREP.md 与基线固化） |

### 2. 占位符扫描

已全文扫描：无 TBD / TODO / 「后续实现」等占位。`data/golden_set.json` 中的 `RESUME_ID` 等是数据模板占位，README 已明确要求替换为真实 ID。

### 3. 类型与命名一致性

- 陪练消息结构统一为 `{role, content, score, feedback}`，服务层、API、前端渲染一致。
- `AnswerEvaluation` 键（`score / feedback / next_question`）与 `InterviewSummary` 键（`overall_score / strengths / weaknesses / improvement_plan`）在 schema、服务、前端一致。
- 评测任务类型统一为 `match / cover_letter / interview`，judge、runner、golden 样例、前端一致。
- 评测指标键（`total_cases / passed_cases / pass_rate / by_type`）在 runner、API 响应、EvalPanel 一致。
- `judge_cover_letter` 复用 `cover_letter_service.JudgeScore`，避免重复定义 schema。
- runner 中 `vector_store` 注入约定与 Phase 1/2 的 `llm` 注入风格一致。
