import re
import statistics
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import JD
from app.utils.text import extract_terms

SALARY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)\s*([kK万])")


def parse_salary(text: str) -> tuple[float, float] | None:
    """解析薪资文本为 (下限k, 上限k)；无法解析返回 None。"""
    m = SALARY_RE.search(text or "")
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    if m.group(3) == "万":
        lo, hi = lo * 10, hi * 10
    return lo, hi


def generate_market_insight(db: Session) -> dict:
    """聚合全部 JD：技能频次、薪资统计、地点与公司分布。确定性输出，不调用 LLM。"""
    jds = db.query(JD).all()
    skills: Counter = Counter()
    locations: Counter = Counter()
    companies: Counter = Counter()
    salary_maxes: list[float] = []
    salary_mins: list[float] = []

    for jd in jds:
        structured = jd.structured_json
        for field in ("requirements", "responsibilities"):
            for item in structured.get(field, []):
                for term in extract_terms(item):
                    if len(term) >= 2:
                        skills[term] += 1
        locations[structured.get("location", "未知")] += 1
        companies[jd.company or "未知"] += 1
        parsed = parse_salary(structured.get("salary", ""))
        if parsed:
            salary_mins.append(parsed[0])
            salary_maxes.append(parsed[1])

    salary_stats = {}
    if salary_maxes:
        salary_stats = {
            "min": min(salary_mins),
            "median": statistics.median(salary_maxes),
            "max": max(salary_maxes),
        }
    return {
        "total_jds": len(jds),
        "top_skills": [
            {"skill": skill, "count": count} for skill, count in skills.most_common(10)
        ],
        "salary_stats": salary_stats,
        "location_counts": dict(locations),
        "company_counts": dict(companies),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
