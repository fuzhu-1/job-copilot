import threading
import time

import fitz


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_upload_then_confirm_flow(client, tmp_path):
    pdf_path = tmp_path / "r.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "姓名：张三", fontname="china-s")
    doc.save(str(pdf_path))
    doc.close()

    with open(pdf_path, "rb") as f:
        res = client.post(
            "/api/resume/upload",
            files={"file": ("r.pdf", f, "application/pdf")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending_confirmation"
    assert data["structured"]["name"] == "张三"

    res2 = client.post(
        f"/api/resume/{data['resume_id']}/confirm",
        json={"structured": data["structured"]},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "confirmed"


def test_create_jd_text(client):
    res = client.post("/api/jds", json={"source": "text", "text": "京东招聘 LLM 应用开发实习生"})
    assert res.status_code == 200
    data = res.json()
    assert data["company"] == "京东"
    assert data["title"] == "LLM 应用开发实习生"


def test_create_jd_url_requires_url(client):
    res = client.post("/api/jds", json={"source": "url", "url": ""})
    assert res.status_code == 400


def test_create_match_returns_task_id(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "run_matches_task", lambda *a, **k: None)
    res = client.post("/api/matches", json={"resume_id": "r1", "jd_ids": ["j1"]})
    assert res.status_code == 200
    assert "task_id" in res.json()


def test_list_jds_filter_by_keyword(client, db_session):
    import json

    import app.main as main_module
    from app.models import JD
    from app.vector_store import COLLECTION_JDS

    jd1 = JD(
        company="京东",
        title="机器学习实习生",
        raw_text="a",
        structured_json={"requirements": ["熟悉机器学习"]},
    )
    jd2 = JD(
        company="字节",
        title="前端开发工程师",
        raw_text="b",
        structured_json={"requirements": ["熟悉前端工程化"]},
    )
    db_session.add_all([jd1, jd2])
    db_session.commit()
    main_module.vector_store.add(
        COLLECTION_JDS,
        [json.dumps(jd1.structured_json, ensure_ascii=False), json.dumps(jd2.structured_json, ensure_ascii=False)],
        [jd1.id, jd2.id],
        [{"jd_id": jd1.id}, {"jd_id": jd2.id}],
    )
    res = client.get("/api/jds?q=机器学习")
    assert res.status_code == 200
    titles = [jd["title"] for jd in res.json()["jds"]]
    assert "机器学习实习生" in titles
    assert "前端开发工程师" not in titles


def test_cover_letter_missing_match_returns_404(client):
    res = client.post(
        "/api/matches/missing/cover-letter",
        json={"match_id": "missing", "tone": "standard"},
    )
    assert res.status_code == 404


from app.models import MatchTask


def test_create_match_persists_task_row(client, db_session, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "run_matches_task", lambda *a, **k: None)
    res = client.post("/api/matches", json={"resume_id": "r1", "jd_ids": ["j1"]})
    assert res.status_code == 200
    task = db_session.get(MatchTask, res.json()["task_id"])
    assert task is not None
    assert task.status == "running"
    assert task.jd_ids_json == ["j1"]


def test_sse_replays_persisted_events(client, db_session):
    task = MatchTask(
        id="t-replay",
        resume_id="r1",
        jd_ids_json=["j1"],
        status="completed",
        events_json=[
            {"type": "started", "total": 1, "seq": 1},
            {"type": "match_result", "result": {"match_id": "m1"}, "seq": 2},
            {"type": "completed", "seq": 3},
        ],
    )
    db_session.add(task)
    db_session.commit()
    with client.stream("GET", "/api/matches/t-replay/stream") as response:
        body = b"".join(response.iter_bytes()).decode()
    assert "started" in body
    assert "match_result" in body
    assert "completed" in body


def test_recover_interrupted_tasks(db_session):
    from app.main import recover_interrupted_tasks

    task = MatchTask(id="t-stale", resume_id="r", jd_ids_json=[], status="running", events_json=[])
    db_session.add(task)
    db_session.commit()
    recover_interrupted_tasks(db_session)
    recovered = db_session.get(MatchTask, "t-stale")
    assert recovered.status == "error"
    assert "服务重启" in recovered.error


def test_sse_missing_task_404(client):
    res = client.get("/api/matches/nope/stream")
    assert res.status_code == 404


def test_batch_delete_jd_cascades(client, db_session):
    from app.models import Application, JD, Match, Resume

    resume = Resume(raw_text="r", structured_json={}, status="confirmed")
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={})
    db_session.add_all([resume, jd])
    db_session.commit()
    match = Match(resume_id=resume.id, jd_id=jd.id, total_score=80.0)
    db_session.add(match)
    db_session.commit()
    app_row = Application(match_id=match.id, current_status="applied", status_history_json=[])
    db_session.add(app_row)
    db_session.commit()
    match_id = match.id
    app_id = app_row.id

    res = client.post("/api/jds/batch-delete", json={"jd_ids": [jd.id]})
    assert res.status_code == 200
    assert res.json()["deleted"] == 1
    db_session.expire_all()
    assert db_session.query(Match).filter(Match.id == match_id).count() == 0
    assert db_session.query(Application).filter(Application.id == app_id).count() == 0


def test_upload_failure_cleans_orphan_file(client, db_session, monkeypatch, tmp_path):
    import app.main as main_module

    def boom(*a, **k):
        raise RuntimeError("parse failed")

    monkeypatch.setattr(main_module.resume_service, "create_resume_from_file", boom)
    upload_dir = main_module.Path(main_module.settings.upload_dir)
    before = set(upload_dir.glob("*.pdf"))
    pdf_path = tmp_path / "bad.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 fake")
    with open(pdf_path, "rb") as f:
        res = client.post(
            "/api/resume/upload", files={"file": ("bad.pdf", f, "application/pdf")}
        )
    assert res.status_code == 422
    after = set(upload_dir.glob("*.pdf"))
    assert after == before  # 失败后不留孤儿文件


def test_run_matches_task_marks_completed(db_session, monkeypatch):
    import app.main as main_module
    from app.models import MatchTask
    from app.schemas import MatchResult
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    task = MatchTask(id="t-done", resume_id="r", jd_ids_json=["j"], status="running", events_json=[])
    s = Session()
    s.add(task)
    s.commit()

    def fake_run_match(db, resume_id, jd_id, vector_store, llm=None):
        return MatchResult(match_id="m1", jd_id=jd_id, jd_name="x", total_score=80.0)

    monkeypatch.setattr(main_module.match_service, "run_match", fake_run_match)
    main_module.run_matches_task("t-done", "r", ["j"], session_factory=Session)
    s.expire_all()
    finished = s.get(MatchTask, "t-done")
    assert finished.status == "completed"
    assert [e["type"] for e in finished.events_json] == [
        "started",
        "match_progress",
        "match_result",
        "completed",
    ]
    s.close()


def test_sse_live_update(client, db_session):
    from app.models import MatchTask
    from sqlalchemy.orm import sessionmaker

    task = MatchTask(
        id="t-live",
        resume_id="r",
        jd_ids_json=["j"],
        status="running",
        events_json=[{"type": "started", "seq": 1}],
    )
    db_session.add(task)
    db_session.commit()
    Session = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)

    def pub():
        time.sleep(0.5)
        s = Session()
        t = s.get(MatchTask, "t-live")
        t.events_json = list(t.events_json) + [{"type": "completed", "seq": 2}]
        s.commit()
        s.close()

    threading.Thread(target=pub, daemon=True).start()
    with client.stream("GET", "/api/matches/t-live/stream") as response:
        body = b"".join(response.iter_bytes()).decode()
    assert "completed" in body
