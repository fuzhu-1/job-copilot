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
