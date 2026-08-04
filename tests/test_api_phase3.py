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
