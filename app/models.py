import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(20), default="file")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending_confirmation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JD(Base):
    __tablename__ = "jds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(20), default="text")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id"))
    jd_id: Mapped[str] = mapped_column(ForeignKey("jds.id"))
    dimension_scores_json: Mapped[dict] = mapped_column(JSON, default=dict)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    gaps_json: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    current_status: Mapped[str] = mapped_column(String(30), default="applied")
    status_history_json: Mapped[list] = mapped_column(JSON, default=list)
    custom_statuses_json: Mapped[dict] = mapped_column(JSON, default=dict)
    next_action: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class JDReport(Base):
    __tablename__ = "jd_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    jd_id: Mapped[str | None] = mapped_column(ForeignKey("jds.id"), nullable=True)
    report_type: Mapped[str] = mapped_column(String(30))  # company_research | market_insight
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    jd_id: Mapped[str] = mapped_column(ForeignKey("jds.id"))
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id"))
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    messages_json: Mapped[list] = mapped_column(JSON, default=list)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), default="")
    task_type: Mapped[str] = mapped_column(String(30))  # match | cover_letter | interview
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
