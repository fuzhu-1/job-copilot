import json

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.llm import LLMService
from app.models import JD, Match, Resume


class JudgeScore(BaseModel):
    score: float = 0.0
    feedback: str = ""


COVER_LETTER_TONES = {
    "standard": "语气专业平实",
    "warm": "语气热情有感染力",
    "concise": "内容精炼、要点突出",
}


def generate_cover_letter(
    db: Session,
    match_id: str,
    tone: str = "standard",
    llm: LLMService | None = None,
) -> dict:
    llm = llm or LLMService()
    match = db.get(Match, match_id)
    if match is None:
        raise KeyError(f"match not found: {match_id}")
    resume = db.get(Resume, match.resume_id)
    jd = db.get(JD, match.jd_id)
    if resume is None or jd is None:
        raise KeyError("resume or jd not found")

    tone_desc = COVER_LETTER_TONES.get(tone, COVER_LETTER_TONES["standard"])
    draft = _draft(resume, jd, match, tone_desc, llm, feedback=None)
    score = _judge(draft, jd, llm)
    revised = False
    if score < 0.8:
        draft = _draft(
            resume,
            jd,
            match,
            tone_desc,
            llm,
            feedback=f"上一版质量分 {score:.2f}，请改进后重新生成。",
        )
        score = _judge(draft, jd, llm)
        revised = True
    return {"content": draft, "judge_score": score, "revised": revised}


def _draft(resume: Resume, jd: JD, match: Match, tone_desc: str, llm: LLMService, feedback: str | None) -> str:
    prompt = (
        f"请写一封求职自荐信（{tone_desc}），300-400 字。\n"
        f"候选人：{json.dumps(resume.structured_json, ensure_ascii=False)}\n"
        f"岗位：{jd.company} {jd.title}\n"
        f"JD 要点：{json.dumps(jd.structured_json, ensure_ascii=False)}\n"
        f"匹配总分 {match.total_score}，维度分 {match.dimension_scores_json}，差距 {match.gaps_json}\n"
        "写作要求：开头点明申请意向；正文用 2-3 个与 JD 直接相关的经历/项目亮点（尽量量化）；"
        "如有明显差距，用一句学习意愿或迁移能力补强；结尾礼貌收束。"
    )
    if feedback:
        prompt += f"\n评审反馈：{feedback}"
    return llm.complete([{"role": "user", "content": prompt}])


def _judge(draft: str, jd: JD, llm: LLMService) -> float:
    prompt = (
        "你是自荐信评审。按 rubric 打分（0-1 分，保留两位小数）：\n"
        "1) 覆盖 JD 关键要求 2) 有量化成果 3) 结构完整（开头-正文-结尾）4) 语言得体\n"
        f"JD：{json.dumps(jd.structured_json, ensure_ascii=False)}\n"
        f"自荐信：\n{draft}\n"
        '输出 JSON：{"score": 0.0-1.0, "feedback": "改进建议"}'
    )
    data = llm.complete_structured([{"role": "user", "content": prompt}], JudgeScore)
    return float(data["score"])
