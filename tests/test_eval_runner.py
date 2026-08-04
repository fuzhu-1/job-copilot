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
