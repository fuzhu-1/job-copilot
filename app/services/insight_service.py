import re
import statistics
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import JD
from app.utils.text import extract_terms

SALARY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)\s*([kK万])")

INSIGHT_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have", "has", "you", "your",
    "will", "can", "job", "work", "year", "years", "experience", "skill", "skills",
    "good", "strong", "ability", "etc", "e.g", "bad", "case", "use", "used", "using",
    "able", "related", "familiar", "knowledge", "excellent", "team", "design", "development",
    "related", "preferred", "plus", "including", "such", "also", "etc",
}


def parse_salary(text: str) -> tuple[float, float] | None:
    """解析薪资文本为 (下限k, 上限k)；无法解析返回 None。"""
    m = SALARY_RE.search(text or "")
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    if m.group(3) == "万":
        lo, hi = lo * 10, hi * 10
    return lo, hi


def generate_market_insight(db: Session, llm=None) -> dict:
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
                    if (
                        len(term) >= 2
                        and re.fullmatch(r"\d+([-+/]\d+)*", term) is None
                        and term.lower() not in INSIGHT_STOPWORDS
                    ):
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
    report = {
        "total_jds": len(jds),
        "top_skills": [
            {"skill": skill, "count": count} for skill, count in skills.most_common(10)
        ],
        "salary_stats": salary_stats,
        "location_counts": dict(locations),
        "company_counts": dict(companies),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if llm is not None:
        report["narrative"] = _narrative(llm, report)
    return report


def _narrative(llm, report: dict) -> str:
    skills_text = "、".join(f"{s['skill']}({s['count']})" for s in report["top_skills"][:6]) or "暂无"
    salary_text = (
        f"薪资中位数 {report['salary_stats']['median']}k"
        if report.get("salary_stats")
        else "薪资信息不足"
    )
    prompt = (
        "你是招聘市场分析师。基于以下岗位聚合数据，用 2-3 句中文给出市场解读，"
        "指出技能趋势与对求职者的建议，不要编造数据。\n"
        f"岗位总数：{report['total_jds']}\n"
        f"热门技能：{skills_text}\n"
        f"薪资：{salary_text}\n"
        f"城市分布：{report.get('location_counts', {})}\n"
        f"公司分布：{report.get('company_counts', {})}"
    )
    return llm.complete([{"role": "user", "content": prompt}]).strip()
