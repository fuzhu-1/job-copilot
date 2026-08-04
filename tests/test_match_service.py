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
    assert result.jd_name == "京东 · 实习生"


def test_run_match_missing_resume_raises(db_session, vector_store):
    import pytest

    with pytest.raises(KeyError):
        run_match(db_session, "nope", "nope", vector_store, llm=FakeLLM())
