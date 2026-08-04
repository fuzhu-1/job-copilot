from datetime import datetime, timedelta, timezone

import pytest

from app.models import Application, JD, Match, Resume
from app.services.application_service import (
    allowed_next,
    create_application,
    follow_up_suggestion,
    get_reminders,
    list_applications,
    register_custom_status,
    transition,
)


def _make_match(db_session):
    resume = Resume(raw_text="r", structured_json={}, status="confirmed")
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=83.0)
    db_session.add(match)
    db_session.commit()
    return match.id


def test_create_application(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id, notes="备注")
    assert app.current_status == "applied"
    assert len(app.status_history_json) == 1
    assert app.notes == "备注"
    assert list_applications(db_session)[0]["jd_name"] == "京东 · 实习生"


def test_transition_valid(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    app = transition(db_session, app.id, "screening", note="进入笔试")
    assert app.current_status == "screening"
    assert len(app.status_history_json) == 2


def test_transition_illegal_raises(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    with pytest.raises(ValueError):
        transition(db_session, app.id, "offer")


def test_custom_status_enables_transition(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    app = register_custom_status(db_session, app.id, "offer_pending", "applied", ["offer"])
    assert "offer_pending" in app.custom_statuses_json["applied"]
    app = transition(db_session, app.id, "offer_pending")
    assert app.current_status == "offer_pending"
    app = transition(db_session, app.id, "offer")
    assert app.current_status == "offer"


def test_follow_up_suggestion_by_status():
    old = datetime.now(timezone.utc) - timedelta(days=10)
    applied = Application(
        current_status="applied",
        status_history_json=[{"status": "applied", "at": old.isoformat()}],
    )
    assert "建议" in follow_up_suggestion(applied)
    fresh = Application(
        current_status="applied",
        status_history_json=[{"status": "applied", "at": datetime.now(timezone.utc).isoformat()}],
    )
    assert follow_up_suggestion(fresh) == ""


def test_reminders_include_overdue(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    old = datetime.now(timezone.utc) - timedelta(days=5)
    app.status_history_json = [{"status": "applied", "at": old.isoformat()}]
    db_session.commit()
    reminders = get_reminders(db_session)
    assert any(r["application_id"] == app.id for r in reminders)
    assert list_applications(db_session)[0]["waiting_days"] >= 5


def test_register_custom_status_deduplicates(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    app = register_custom_status(db_session, app.id, "offer_pending", "applied", ["offer"])
    app = register_custom_status(db_session, app.id, "offer_pending", "applied", ["offer"])
    assert app.custom_statuses_json["applied"].count("offer_pending") == 1


def test_allowed_next_excludes_current_self_loop(db_session):
    match_id = _make_match(db_session)
    app = create_application(db_session, match_id)
    app = register_custom_status(db_session, app.id, "1", "applied", ["1"])
    app = transition(db_session, app.id, "1")
    assert app.current_status == "1"
    assert allowed_next(app) == []
