import threading
import time

import fitz

from app.events import event_bus


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


def test_cover_letter_missing_match_returns_404(client):
    res = client.post(
        "/api/matches/missing/cover-letter",
        json={"match_id": "missing", "tone": "standard"},
    )
    assert res.status_code == 404


def test_sse_stream_delivers_completed_event(client):
    task_id = "sse-test-1"

    def pub():
        time.sleep(0.2)
        event_bus.publish(task_id, {"type": "completed"})

    threading.Thread(target=pub, daemon=True).start()
    with client.stream("GET", f"/api/matches/{task_id}/stream") as response:
        body = b"".join(response.iter_bytes()).decode()
    assert "completed" in body
