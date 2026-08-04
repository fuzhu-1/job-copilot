from app.models import JD, JDReport
from app.services.research_service import generate_company_report


class FakeSearch:
    def search(self, query, top_k=5):
        return [{"title": "t", "url": "u", "content": "面试流程：两轮技术面+一轮 HR"}]


class FakeSearchEmpty:
    def search(self, query, top_k=5):
        return []


class FakeLLM:
    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(
            {
                "company": "京东",
                "business_lines": ["零售", "物流"],
                "interview_process": "两轮技术面+一轮 HR",
                "salary_reference": "20-40K",
                "team_background": "大模型团队",
                "tips": ["准备 RAG 项目经历"],
                "source_note": "基于搜索与模型知识",
            }
        ).model_dump()


def test_generate_company_report_persists(db_session):
    jd = JD(
        company="京东",
        title="LLM 应用开发实习生",
        raw_text="j",
        structured_json={"company": "京东", "title": "LLM 应用开发实习生"},
    )
    db_session.add(jd)
    db_session.commit()

    report = generate_company_report(db_session, jd.id, llm=FakeLLM(), search=FakeSearch())
    assert report["company"] == "京东"
    assert report["interview_process"] == "两轮技术面+一轮 HR"
    stored = db_session.query(JDReport).filter_by(jd_id=jd.id).one()
    assert stored.report_type == "company_research"
    assert stored.report_json["company"] == "京东"


def test_generate_company_report_no_search(db_session):
    jd = JD(company="京东", title="实习生", raw_text="j", structured_json={"company": "京东"})
    db_session.add(jd)
    db_session.commit()
    report = generate_company_report(
        db_session, jd.id, llm=FakeLLM(), search=FakeSearchEmpty()
    )
    assert report["source_note"]  # 无搜索结果时提示降级
