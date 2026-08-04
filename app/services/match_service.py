import json

from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import JD, Match, Resume
from app.schemas import DimensionScores, MatchResult
from app.vector_store import VectorStore
from app.workflow.graph import build_match_graph


def run_match(
    db: Session,
    resume_id: str,
    jd_id: str,
    vector_store: VectorStore,
    llm: LLMService | None = None,
) -> MatchResult:
    resume = db.get(Resume, resume_id)
    jd = db.get(JD, jd_id)
    if resume is None:
        raise KeyError(f"resume not found: {resume_id}")
    if jd is None:
        raise KeyError(f"jd not found: {jd_id}")

    graph = build_match_graph(llm)
    state = {
        "resume_text": json.dumps(resume.structured_json, ensure_ascii=False),
        "jd_text": json.dumps(jd.structured_json, ensure_ascii=False),
    }
    result = graph.invoke(state)

    match = Match(
        resume_id=resume_id,
        jd_id=jd_id,
        dimension_scores_json=result["dimension_scores"],
        total_score=result["total_score"],
        gaps_json=result["gaps"],
        summary=result["summary"],
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return MatchResult(
        match_id=match.id,
        jd_id=jd_id,
        dimension_scores=DimensionScores(**result["dimension_scores"]),
        reasons=result["reasons"],
        total_score=result["total_score"],
        gaps=result["gaps"],
        summary=result["summary"],
    )
