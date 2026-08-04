import json

from sqlalchemy.orm import Session

from app.agents.research_agent import generate_report
from app.llm import LLMService
from app.models import JD, JDReport
from app.tools.search import SearchTool


def generate_company_report(
    db: Session,
    jd_id: str,
    llm: LLMService | None = None,
    search: SearchTool | None = None,
) -> dict:
    jd = db.get(JD, jd_id)
    if jd is None:
        raise KeyError(f"jd not found: {jd_id}")
    llm = llm or LLMService()
    search = search or SearchTool()
    snippets = search.search(f"{jd.company} 面试流程 薪资 团队 招聘", top_k=5)
    report = generate_report(
        company=jd.company or jd.structured_json.get("company", ""),
        title=jd.title or jd.structured_json.get("title", ""),
        jd_summary=json.dumps(jd.structured_json, ensure_ascii=False)[:2000],
        snippets=snippets,
        llm=llm,
    )
    db.add(JDReport(jd_id=jd_id, report_type="company_research", report_json=report))
    db.commit()
    return report
