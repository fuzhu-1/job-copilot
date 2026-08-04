from app.schemas import MatchResult
from app.services.cover_letter_service import JudgeScore


def judge_match(result: MatchResult, expected: dict) -> dict:
    """确定性判定：总分在期望区间内，且差距均被期望覆盖。"""
    lo = expected.get("total_min", 0)
    hi = expected.get("total_max", 100)
    total = result.total_score
    in_range = lo <= total <= hi
    expected_gaps = expected.get("gaps", [])
    gaps_ok = True
    if expected_gaps:
        gaps_ok = all(any(g in exp for exp in expected_gaps) for g in result.gaps)
    return {
        "task_type": "match",
        "score": total,
        "passed": in_range and gaps_ok,
        "detail": f"total={total}, range=[{lo},{hi}], gaps_ok={gaps_ok}",
    }


def judge_interview(summary: dict, expected: dict) -> dict:
    """确定性判定：总结总分不低于阈值。"""
    overall = float(summary.get("overall_score", 0))
    min_score = expected.get("min_score", 60)
    return {
        "task_type": "interview",
        "score": overall,
        "passed": overall >= min_score,
        "detail": f"overall={overall}, min={min_score}",
    }


def judge_cover_letter(content: str, expected: dict, llm) -> dict:
    """LLM-as-judge：rubric 打分 + 关键词覆盖。"""
    keywords = expected.get("keywords", [])
    missing = [k for k in keywords if k not in content]
    min_score = expected.get("min_score", 0.8)
    prompt = (
        "你是自荐信评审。按 rubric 打分（0-1 分，保留两位小数）：\n"
        "1) 覆盖 JD 关键要求 2) 有量化成果 3) 结构完整 4) 语言得体\n"
        f"自荐信：\n{content[:4000]}\n"
        '输出 JSON：{"score": 0.0-1.0, "feedback": "改进建议"}'
    )
    data = llm.complete_structured([{"role": "user", "content": prompt}], JudgeScore)
    score = float(data["score"])
    return {
        "task_type": "cover_letter",
        "score": round(score, 2),
        "passed": score >= min_score and not missing,
        "missing_keywords": missing,
        "detail": f"judge={score:.2f}, min={min_score}",
    }
