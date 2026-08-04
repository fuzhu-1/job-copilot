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
