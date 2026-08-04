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
