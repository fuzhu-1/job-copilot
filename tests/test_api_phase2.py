from app.models import JD, Match, Resume


def _make_match(db_session):
    resume = Resume(raw_text="r", structured_json={"skills": ["Python"]}, status="confirmed")
    jd = JD(
        company="京东",
        title="LLM 应用开发实习生",
        raw_text="j",
        structured_json={
            "company": "京东",
            "title": "LLM 应用开发实习生",
            "location": "北京",
            "salary": "20-40K·14薪",
            "requirements": ["Python", "LangGraph"],
        },
    )
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=83.0)
    db_session.add(match)
    db_session.commit()
    return match.id, jd.id


def test_application_flow(client, db_session):
    match_id, _ = _make_match(db_session)
    res = client.post("/api/applications", json={"match_id": match_id, "notes": "备注"})
    assert res.status_code == 200
    app_id = res.json()["application_id"]
    assert res.json()["current_status"] == "applied"

    res2 = client.post(
        f"/api/applications/{app_id}/status",
        json={"target_status": "screening", "note": "进入笔试"},
    )
    assert res2.status_code == 200
    assert res2.json()["current_status"] == "screening"
    assert len(res2.json()["status_history"]) == 2

    res3 = client.post(f"/api/applications/{app_id}/status", json={"target_status": "offer"})
    assert res3.status_code == 422


def test_application_custom_status(client, db_session):
    match_id, _ = _make_match(db_session)
    app_id = client.post("/api/applications", json={"match_id": match_id}).json()["application_id"]
    res = client.post(
        f"/api/applications/{app_id}/custom-statuses",
        json={"status": "offer_pending", "from_status": "applied", "next": ["offer"]},
    )
    assert res.status_code == 200
    assert "offer_pending" in res.json()["custom_statuses"]["applied"]
    res2 = client.post(f"/api/applications/{app_id}/status", json={"target_status": "offer_pending"})
    assert res2.status_code == 200
    assert res2.json()["current_status"] == "offer_pending"


def test_application_list_and_reminders(client, db_session):
    match_id, _ = _make_match(db_session)
    client.post("/api/applications", json={"match_id": match_id})
    res = client.get("/api/applications")
    assert res.status_code == 200
    assert len(res.json()["applications"]) == 1
    res2 = client.get("/api/applications/reminders")
    assert res2.status_code == 200
    assert isinstance(res2.json()["reminders"], list)
