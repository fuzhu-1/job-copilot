from app.models import Application, InterviewSession, JD, JDReport, Match, Resume


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
