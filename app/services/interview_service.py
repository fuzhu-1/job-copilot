import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import InterviewSession, JD, Resume
from app.schemas import AnswerEvaluation, InterviewSummary

MAX_TURNS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summary(jd: JD, resume: Resume) -> str:
    return (
        f"JD：{json.dumps(jd.structured_json, ensure_ascii=False)}\n"
        f"简历：{json.dumps(resume.structured_json, ensure_ascii=False)}"
    )[:8000]


def create_session(
    db: Session, jd_id: str, resume_id: str, llm: LLMService | None = None
) -> InterviewSession:
    llm = llm or LLMService()
    jd = db.get(JD, jd_id)
    resume = db.get(Resume, resume_id)
    if jd is None:
        raise KeyError(f"jd not found: {jd_id}")
    if resume is None:
        raise KeyError(f"resume not found: {resume_id}")
    first_question = llm.complete(
        [
            {
                "role": "system",
                "content": "你是资深面试官。基于岗位 JD 与候选人简历，生成第一个面试问题。"
                "问题要贴合岗位要求，并尽量结合候选人项目经历。只输出问题本身。",
            },
            {"role": "user", "content": _summary(jd, resume)},
        ]
    )
    session = InterviewSession(
        jd_id=jd_id,
        resume_id=resume_id,
        status="active",
        messages_json=[
            {"role": "assistant", "content": first_question, "score": None, "feedback": None}
        ],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def respond(
    db: Session, session_id: str, answer: str, llm: LLMService | None = None
) -> dict:
    llm = llm or LLMService()
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise KeyError(f"interview session not found: {session_id}")
    if session.status != "active":
        raise ValueError("面试会话已结束")

    messages = list(session.messages_json)
    messages.append({"role": "user", "content": answer, "score": None, "feedback": None})
    jd = db.get(JD, session.jd_id)
    resume = db.get(Resume, session.resume_id)
    last_question = next(
        m["content"] for m in reversed(messages) if m["role"] == "assistant"
    )
    evaluation = llm.complete_structured(
        [
            {
                "role": "system",
                "content": "你是面试评分官。根据面试问题与候选人回答评分并给出 STAR 反馈，然后生成追问或下一题。"
                "输出 JSON：score(0-100)、feedback(结构/内容/量化建议)、next_question(追问或下一题)。",
            },
            {
                "role": "user",
                "content": (
                    f"{_summary(jd, resume)}\n"
                    f"面试问题：{last_question}\n候选人回答：{answer}"
                ),
            },
        ],
        AnswerEvaluation,
    )
    score = float(evaluation["score"])
    feedback = evaluation["feedback"]
    next_question = evaluation["next_question"]

    assistant_turns = [m for m in messages if m["role"] == "assistant"]
    completed = len(assistant_turns) >= MAX_TURNS
    closing = "（面试结束，正在生成总结）" if completed else next_question
    messages.append(
        {"role": "assistant", "content": closing, "score": score, "feedback": feedback}
    )
    session.messages_json = messages
    session.updated_at = _now()

    result = {
        "score": score,
        "feedback": feedback,
        "next_question": next_question,
        "completed": completed,
        "summary": None,
    }
    if completed:
        session.status = "completed"
        summary = _summarize(session, jd, resume, llm)
        session.summary_json = summary
        result["summary"] = summary

    db.commit()
    db.refresh(session)
    return result


def _summarize(session: InterviewSession, jd: JD, resume: Resume, llm: LLMService) -> dict:
    transcript = json.dumps(session.messages_json, ensure_ascii=False)[:12000]
    return llm.complete_structured(
        [
            {
                "role": "system",
                "content": "你是面试复盘教练。基于完整对话生成总结，输出 JSON："
                "overall_score(0-100)、strengths、weaknesses、improvement_plan。",
            },
            {"role": "user", "content": f"{_summary(jd, resume)}\n对话记录：\n{transcript}"},
        ],
        InterviewSummary,
    )


def get_session_payload(session: InterviewSession) -> dict:
    return {
        "session_id": session.id,
        "jd_id": session.jd_id,
        "resume_id": session.resume_id,
        "status": session.status,
        "messages": session.messages_json,
        "summary": session.summary_json,
        "created_at": session.created_at.isoformat(),
    }
