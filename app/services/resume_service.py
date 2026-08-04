import json

from sqlalchemy.orm import Session

from app.agents.resume_agent import parse_resume_pdf
from app.llm import LLMService
from app.models import Resume
from app.vector_store import COLLECTION_RESUMES, VectorStore


def create_resume_from_file(
    db: Session,
    file_path: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> Resume:
    raw_text, structured = parse_resume_pdf(file_path, llm)
    resume = Resume(
        source_type="file",
        file_path=file_path,
        raw_text=raw_text,
        structured_json=structured,
        status="pending_confirmation",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def confirm_resume(
    db: Session,
    resume_id: str,
    structured_json: dict,
    vector_store: VectorStore,
) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise KeyError(f"resume not found: {resume_id}")
    resume.structured_json = structured_json
    resume.status = "confirmed"
    db.commit()
    db.refresh(resume)
    vector_store.add(
        COLLECTION_RESUMES,
        [json.dumps(structured_json, ensure_ascii=False)],
        [resume.id],
        [{"resume_id": resume.id}],
    )
    return resume
