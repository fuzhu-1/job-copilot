from app.models import JD, Match, Resume


def test_resume_crud(db_session):
    resume = Resume(
        source_type="file",
        raw_text="hello",
        structured_json={"name": "张三"},
        status="pending_confirmation",
    )
    db_session.add(resume)
    db_session.commit()
    loaded = db_session.get(Resume, resume.id)
    assert loaded.status == "pending_confirmation"
    assert loaded.structured_json["name"] == "张三"


def test_match_persists_scores_and_gaps(db_session):
    resume = Resume(raw_text="r", structured_json={})
    jd = JD(company="京东", title="LLM 应用开发实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(
        resume_id=resume.id,
        jd_id=jd.id,
        total_score=88.0,
        gaps_json=["缺少企业级项目经验"],
    )
    db_session.add(match)
    db_session.commit()
    loaded = db_session.get(Match, match.id)
    assert loaded.total_score == 88.0
    assert loaded.gaps_json == ["缺少企业级项目经验"]
