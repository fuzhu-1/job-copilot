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


def test_list_interviews(client, db_session, monkeypatch):
    import app.main as main_module

    class FakeLLM:
        def complete(self, messages, max_tokens=2000):
            return "请介绍一个你做过的大模型项目"

        def complete_structured(self, messages, schema, max_tokens=2000):
            if schema.__name__ == "AnswerEvaluation":
                return schema.model_validate(
                    {"score": 85.0, "feedback": "ok", "next_question": "追问"}
                ).model_dump()
            if schema.__name__ == "InterviewSummary":
                return schema.model_validate(
                    {
                        "overall_score": 82.0,
                        "strengths": [],
                        "weaknesses": [],
                        "improvement_plan": [],
                    }
                ).model_dump()
            raise AssertionError(schema.__name__)

    monkeypatch.setattr(main_module, "llm", FakeLLM())
    jd_id, resume_id = _setup(client, db_session)
    client.post("/api/interviews/sessions", json={"jd_id": jd_id, "resume_id": resume_id})
    res = client.get("/api/interviews/sessions")
    assert res.status_code == 200
    assert len(res.json()["sessions"]) == 1
    assert res.json()["sessions"][0]["jd_name"] == "京东 · LLM 实习生"


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
