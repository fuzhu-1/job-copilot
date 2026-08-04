import asyncio
import json
import queue as queue_module
import threading
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.agents import supervisor as supervisor_agent
from app.db import SessionLocal, get_session
from app.events import event_bus
from app.llm import LLMService
from app.schemas import (
    AgentMessage,
    ApplicationCreate,
    ApplicationTransition,
    CoverLetterRequest,
    CustomStatusCreate,
    MatchRequest,
)
from app.services import (
    application_service,
    cover_letter_service,
    insight_service,
    jd_service,
    match_service,
    research_service,
    resume_service,
)
from app.vector_store import VectorStore

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

vector_store = VectorStore()
llm = LLMService()


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
def list_jds(db: Session = Depends(get_session)):
    from app.models import JD

    jds = db.query(JD).order_by(JD.created_at.desc()).limit(50).all()
    return {
        "jds": [
            {
                "jd_id": jd.id,
                "company": jd.company,
                "title": jd.title,
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


@app.post("/api/insights/market")
def market_insight(db: Session = Depends(get_session)):
    from app.models import JDReport

    report = insight_service.generate_market_insight(db)
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


def run_matches_task(task_id: str, resume_id: str, jd_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        event_bus.publish(task_id, {"type": "started", "total": len(jd_ids)})
        for index, jd_id in enumerate(jd_ids):
            event_bus.publish(
                task_id,
                {"type": "match_progress", "index": index, "total": len(jd_ids), "jd_id": jd_id},
            )
            result = match_service.run_match(db, resume_id, jd_id, vector_store, llm=llm)
            event_bus.publish(task_id, {"type": "match_result", "result": result.model_dump()})
        event_bus.publish(task_id, {"type": "completed"})
    except Exception as exc:
        event_bus.publish(task_id, {"type": "error", "message": str(exc)})
    finally:
        db.close()


@app.post("/api/matches")
def create_match(payload: MatchRequest):
    task_id = uuid.uuid4().hex
    threading.Thread(
        target=run_matches_task,
        args=(task_id, payload.resume_id, payload.jd_ids),
        daemon=True,
    ).start()
    return {"task_id": task_id}


@app.get("/api/matches/{task_id}/stream")
async def match_stream(task_id: str):
    q = event_bus.subscribe(task_id)

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.to_thread(q.get, True, 0.5)
                except queue_module.Empty:
                    continue
                yield {"event": event["type"], "data": json.dumps(event, ensure_ascii=False)}
                if event["type"] in ("completed", "error"):
                    break
        finally:
            event_bus.unsubscribe(task_id, q)

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
    return application_service.to_payload(application)


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
    return application_service.to_payload(application)


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
    return application_service.to_payload(application)


@app.post("/api/agent/message")
def agent_message(payload: AgentMessage, db: Session = Depends(get_session)):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message 必填")
    return supervisor_agent.handle_message(db, message, llm=llm)


web_dist = Path(__file__).resolve().parent / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
