import asyncio
import json
import threading
import uuid
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.agents import supervisor as supervisor_agent
from app.db import SessionLocal, get_session
from app.eval.golden import sync_golden_set
from app.eval.runner import run_eval
from app.llm import LLMService
from app.models import MatchTask
from app.schemas import (
    AgentMessage,
    ApplicationCreate,
    ApplicationTransition,
    CoverLetterRequest,
    CustomStatusCreate,
    InterviewCreate,
    InterviewNoteCreate,
    InterviewRespond,
    MatchRequest,
)
from app.services import (
    application_service,
    cover_letter_service,
    interview_service,
    insight_service,
    jd_service,
    match_service,
    research_service,
    resume_service,
)
from app.models import EvalRun, InterviewSession
from app.models import jd_display_name
from app.tools.search import SearchTool
from app.vector_store import COLLECTION_JDS, VectorStore

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

vector_store = VectorStore()
llm = LLMService()
search_tool = SearchTool()


@app.on_event("startup")
def on_startup() -> None:
    from app.db import Base, engine

    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/resume/upload")
def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_session)):
    suffix = Path(file.filename or "resume.pdf").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    file_path.write_bytes(file.file.read())
    try:
        resume = resume_service.create_resume_from_file(db, str(file_path), vector_store, llm=llm)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"简历解析失败: {exc}") from exc
    return {
        "resume_id": resume.id,
        "status": resume.status,
        "structured": resume.structured_json,
    }


@app.post("/api/resume/{resume_id}/confirm")
def confirm_resume(resume_id: str, payload: dict, db: Session = Depends(get_session)):
    try:
        resume = resume_service.confirm_resume(
            db, resume_id, payload.get("structured", {}), vector_store
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"resume_id": resume.id, "status": resume.status}


@app.post("/api/jds")
def create_jd(payload: dict, db: Session = Depends(get_session)):
    source = payload.get("source", "text")
    if source == "url":
        url = payload.get("url", "")
        if not url:
            raise HTTPException(status_code=400, detail="url 必填")
        try:
            jd = jd_service.create_jd_from_url(db, url, vector_store, llm=llm)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"JD 抓取失败: {exc}") from exc
    else:
        text = payload.get("text", "")
        if not text.strip():
            raise HTTPException(status_code=400, detail="text 必填")
        jd = jd_service.create_jd_from_text(db, text, vector_store, llm=llm)
    return {
        "jd_id": jd.id,
        "company": jd.company,
        "title": jd.title,
        "structured": jd.structured_json,
    }


@app.get("/api/jds")
def list_jds(q: str = "", db: Session = Depends(get_session)):
    from app.models import JD

    query = db.query(JD)
    if q.strip():
        hits = vector_store.query(COLLECTION_JDS, [q.strip()], top_k=20)
        ids = [h["id"] for h in hits]
        if not ids:
            return {"jds": []}
        query = query.filter(JD.id.in_(ids))
    jds = query.order_by(JD.created_at.desc()).limit(50).all()
    return {
        "jds": [
            {
                "jd_id": jd.id,
                "company": jd.company,
                "title": jd.title,
                "display_name": jd_display_name(jd),
                "source_type": jd.source_type,
            }
            for jd in jds
        ]
    }


@app.post("/api/jds/batch")
def create_jds_batch(payload: dict, db: Session = Depends(get_session)):
    texts = payload.get("texts", [])
    if not isinstance(texts, list) or not texts:
        raise HTTPException(status_code=400, detail="texts 必填且为非空数组")
    jd_ids = []
    for text in texts:
        jd = jd_service.create_jd_from_text(db, text, vector_store, llm=llm)
        jd_ids.append(jd.id)
    return {"jd_ids": jd_ids}


@app.post("/api/jds/batch-delete")
def delete_jds_batch(payload: dict, db: Session = Depends(get_session)):
    from app.models import JD

    jd_ids = payload.get("jd_ids", [])
    if not isinstance(jd_ids, list) or not jd_ids:
        raise HTTPException(status_code=400, detail="jd_ids 必填且为非空数组")
    deleted = db.query(JD).filter(JD.id.in_(jd_ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@app.post("/api/insights/market")
def market_insight(db: Session = Depends(get_session)):
    from app.models import JDReport

    report = insight_service.generate_market_insight(db, llm=llm)
    db.add(JDReport(report_type="market_insight", jd_id=None, report_json=report))
    db.commit()
    return {"report": report}


@app.post("/api/jds/{jd_id}/research")
def company_research(jd_id: str, db: Session = Depends(get_session)):
    try:
        report = research_service.generate_company_report(db, jd_id, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"report": report}


@app.post("/api/jobs/search")
def search_jobs(payload: dict):
    query = (payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 必填")
    top_k = min(int(payload.get("top_k", 5) or 5), 10)
    results = search_tool.search(query, top_k=top_k)
    return {"results": results}


def _now_utc():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _append_task_event(db: Session, task_id: str, event: dict) -> None:
    task = db.get(MatchTask, task_id)
    if task is None:
        return
    events = list(task.events_json)
    event = {**event, "seq": len(events) + 1}
    events.append(event)
    task.events_json = events
    task.updated_at = _now_utc()
    db.commit()


def recover_interrupted_tasks(db: Session) -> int:
    count = (
        db.query(MatchTask)
        .filter(MatchTask.status == "running")
        .update({"status": "error", "error": "服务重启，任务中断"})
    )
    db.commit()
    return count


def run_matches_task(
    task_id: str,
    resume_id: str,
    jd_ids: list[str],
    session_factory=SessionLocal,
) -> None:
    db = session_factory()
    try:
        _append_task_event(db, task_id, {"type": "started", "total": len(jd_ids)})
        for index, jd_id in enumerate(jd_ids):
            _append_task_event(
                db,
                task_id,
                {"type": "match_progress", "index": index, "total": len(jd_ids), "jd_id": jd_id},
            )
            result = match_service.run_match(db, resume_id, jd_id, vector_store, llm=llm)
            _append_task_event(db, task_id, {"type": "match_result", "result": result.model_dump()})
        _append_task_event(db, task_id, {"type": "completed"})
    except Exception as exc:
        _append_task_event(db, task_id, {"type": "error", "message": str(exc)})
        task = db.get(MatchTask, task_id)
        if task is not None:
            task.status = "error"
            task.error = str(exc)
            task.updated_at = _now_utc()
            db.commit()
    finally:
        db.close()


@app.post("/api/matches")
def create_match(payload: MatchRequest, db: Session = Depends(get_session)):
    task_id = uuid.uuid4().hex
    task = MatchTask(
        id=task_id,
        resume_id=payload.resume_id,
        jd_ids_json=payload.jd_ids,
        status="running",
        events_json=[],
    )
    db.add(task)
    db.commit()
    threading.Thread(
        target=run_matches_task,
        args=(task_id, payload.resume_id, payload.jd_ids),
        daemon=True,
    ).start()
    return {"task_id": task_id}


@app.get("/api/matches/{task_id}/stream")
async def match_stream(task_id: str, db: Session = Depends(get_session)):
    task = db.get(MatchTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    async def gen():
        cursor = 0
        while True:
            task = db.get(MatchTask, task_id)
            if task is None:
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"type": "error", "message": "task not found"}, ensure_ascii=False
                    ),
                }
                return
            new_events = [e for e in task.events_json if e.get("seq", 0) > cursor]
            for event in new_events:
                cursor = event["seq"]
                yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
                if event["type"] in ("completed", "error"):
                    return
            await asyncio.sleep(0.5)

    return EventSourceResponse(gen())


@app.post("/api/matches/{match_id}/cover-letter")
def cover_letter(match_id: str, payload: CoverLetterRequest, db: Session = Depends(get_session)):
    try:
        result = cover_letter_service.generate_cover_letter(db, match_id, payload.tone, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@app.post("/api/applications")
def create_application(payload: ApplicationCreate, db: Session = Depends(get_session)):
    try:
        application = application_service.create_application(db, payload.match_id, payload.notes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return application_service.to_payload(
        application, application_service._resolve_jd_name(db, application.match_id)
    )


@app.get("/api/applications")
def list_applications(db: Session = Depends(get_session)):
    return {"applications": application_service.list_applications(db)}


@app.get("/api/applications/reminders")
def application_reminders(db: Session = Depends(get_session)):
    return {"reminders": application_service.get_reminders(db)}


@app.post("/api/applications/{app_id}/status")
def transition_application(
    app_id: str, payload: ApplicationTransition, db: Session = Depends(get_session)
):
    try:
        application = application_service.transition(
            db, app_id, payload.target_status, payload.note
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return application_service.to_payload(
        application, application_service._resolve_jd_name(db, application.match_id)
    )


@app.post("/api/applications/{app_id}/custom-statuses")
def add_custom_status(
    app_id: str, payload: CustomStatusCreate, db: Session = Depends(get_session)
):
    try:
        application = application_service.register_custom_status(
            db, app_id, payload.status, payload.from_status, payload.next
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return application_service.to_payload(
        application, application_service._resolve_jd_name(db, application.match_id)
    )


@app.post("/api/agent/message")
def agent_message(payload: AgentMessage, db: Session = Depends(get_session)):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 必填")
    return supervisor_agent.handle_message(db, message, llm=llm)


@app.post("/api/interviews/sessions")
def create_interview(payload: InterviewCreate, db: Session = Depends(get_session)):
    try:
        session = interview_service.create_session(db, payload.jd_id, payload.resume_id, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return interview_service.get_session_payload(session)


@app.get("/api/interviews/sessions")
def list_interviews(db: Session = Depends(get_session)):
    from app.models import JD

    sessions = (
        db.query(InterviewSession)
        .order_by(InterviewSession.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "sessions": [
            {
                "session_id": s.id,
                "jd_id": s.jd_id,
                "jd_name": jd_display_name(db.get(JD, s.jd_id)) if db.get(JD, s.jd_id) else "",
                "resume_id": s.resume_id,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "overall_score": (s.summary_json or {}).get("overall_score", 0),
            }
            for s in sessions
        ]
    }


@app.get("/api/interviews/notes")
def list_interview_notes(db: Session = Depends(get_session)):
    from app.models import InterviewNote

    notes = (
        db.query(InterviewNote)
        .order_by(InterviewNote.note_date.asc(), InterviewNote.created_at.asc())
        .all()
    )
    return {
        "notes": [
            {
                "note_id": n.id,
                "date": n.note_date,
                "title": n.title,
                "note": n.note,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ]
    }


@app.post("/api/interviews/notes")
def create_interview_note(payload: InterviewNoteCreate, db: Session = Depends(get_session)):
    from app.models import InterviewNote

    note = InterviewNote(note_date=payload.date, title=payload.title, note=payload.note)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "note_id": note.id,
        "date": note.note_date,
        "title": note.title,
        "note": note.note,
    }


@app.delete("/api/interviews/notes/{note_id}")
def delete_interview_note(note_id: str, db: Session = Depends(get_session)):
    from app.models import InterviewNote

    note = db.get(InterviewNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    db.delete(note)
    db.commit()
    return {"deleted": True}


@app.post("/api/interviews/sessions/{session_id}/respond")
def respond_interview(
    session_id: str, payload: InterviewRespond, db: Session = Depends(get_session)
):
    try:
        return interview_service.respond(db, session_id, payload.answer, llm=llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/interviews/sessions/{session_id}")
def get_interview(session_id: str, db: Session = Depends(get_session)):
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return interview_service.get_session_payload(session)


@app.post("/api/eval/golden/sync")
def golden_sync(payload: dict = Body(default={}), db: Session = Depends(get_session)):
    from pathlib import Path as _Path

    default_path = _Path(settings.upload_dir).parent / "golden_set.json"
    path = payload.get("path", str(default_path))
    return sync_golden_set(db, path)


@app.post("/api/eval/runs")
def create_eval_run(db: Session = Depends(get_session)):
    report = run_eval(db, llm=llm, vector_store=vector_store)
    run = EvalRun(status="completed", metrics_json=report["metrics"], report_json=report)
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"run_id": run.id, **report}


@app.get("/api/eval/runs")
def list_eval_runs(db: Session = Depends(get_session)):
    runs = db.query(EvalRun).order_by(EvalRun.created_at.desc()).limit(20).all()
    return {
        "runs": [
            {
                "run_id": run.id,
                "metrics": run.metrics_json,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ]
    }


web_dist = Path(__file__).resolve().parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
