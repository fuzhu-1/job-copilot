from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import EvalCase, InterviewSession
from app.services import cover_letter_service, match_service
from app.eval.judge import judge_cover_letter, judge_interview, judge_match
from app.vector_store import VectorStore


def run_eval(
    db: Session,
    llm: LLMService | None = None,
    vector_store: VectorStore | None = None,
) -> dict:
    """逐条执行 golden set 并聚合指标。单条失败不中断整体。"""
    llm = llm or LLMService()
    cases = db.query(EvalCase).all()
    results = []
    for case in cases:
        try:
            result = _run_case(db, case, llm, vector_store)
        except Exception as exc:
            result = {
                "task_type": case.task_type,
                "score": 0.0,
                "passed": False,
                "detail": f"error: {exc}",
            }
        results.append({"title": case.title, **result})

    by_type: dict[str, dict] = {}
    for r in results:
        bucket = by_type.setdefault(r["task_type"], {"passed": 0, "total": 0, "scores": []})
        bucket["total"] += 1
        bucket["passed"] += 1 if r["passed"] else 0
        bucket["scores"].append(r["score"])
    passed = sum(1 for r in results if r["passed"])
    metrics = {
        "total_cases": len(results),
        "passed_cases": passed,
        "pass_rate": round(passed / len(results), 2) if results else 0.0,
        "by_type": {
            t: {
                "passed": v["passed"],
                "total": v["total"],
                "avg_score": round(sum(v["scores"]) / len(v["scores"]), 2)
                if v["scores"]
                else 0.0,
            }
            for t, v in by_type.items()
        },
    }
    return {"metrics": metrics, "results": results}


def _run_case(db: Session, case: EvalCase, llm: LLMService, vector_store: VectorStore | None) -> dict:
    task_type = case.task_type
    if task_type == "match":
        result = match_service.run_match(
            db,
            case.input_json["resume_id"],
            case.input_json["jd_id"],
            vector_store or VectorStore(),
            llm=llm,
        )
        return judge_match(result, case.expected_json)
    if task_type == "cover_letter":
        match_id = case.input_json["match_id"]
        content = cover_letter_service.generate_cover_letter(
            db, match_id, "standard", llm=llm
        )["content"]
        return judge_cover_letter(content, case.expected_json, llm)
    if task_type == "interview":
        session = db.get(InterviewSession, case.input_json["session_id"])
        if session is None:
            raise KeyError("interview session not found")
        return judge_interview(session.summary_json, case.expected_json)
    raise ValueError(f"unknown task_type: {task_type}")
