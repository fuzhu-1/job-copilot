import json

from sqlalchemy.orm import Session

from app.agents.jd_agent import structure_jd_text
from app.llm import LLMService
from app.models import JD
from app.tools.jd_fetcher import fetch_url_text
from app.vector_store import COLLECTION_JDS, VectorStore


def _store_jd(db: Session, jd: JD, vector_store: VectorStore) -> JD:
    db.add(jd)
    db.commit()
    db.refresh(jd)
    vector_store.add(
        COLLECTION_JDS,
        [json.dumps(jd.structured_json, ensure_ascii=False)],
        [jd.id],
        [{"jd_id": jd.id}],
    )
    return jd


def create_jd_from_text(
    db: Session,
    text: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> JD:
    structured = structure_jd_text(text, llm)
    jd = JD(
        source_type="text",
        raw_text=text,
        company=structured.get("company", ""),
        title=structured.get("title", ""),
        structured_json=structured,
    )
    return _store_jd(db, jd, vector_store)


def create_jd_from_url(
    db: Session,
    url: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> JD:
    text = fetch_url_text(url)
    structured = structure_jd_text(text, llm)
    jd = JD(
        source_type="url",
        source_url=url,
        raw_text=text,
        company=structured.get("company", ""),
        title=structured.get("title", ""),
        structured_json=structured,
    )
    return _store_jd(db, jd, vector_store)
