import fitz

from app.agents.resume_agent import parse_resume_pdf, parse_resume_text
from fixtures_data import RESUME_DATA


class FakeLLM:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def test_parse_resume_text():
    result = parse_resume_text("我叫张三，会 Python 和 LangGraph", FakeLLM(RESUME_DATA))
    assert result["name"] == "张三"
    assert result["skills"] == ["Python", "LangGraph", "FastAPI", "RAG", "SQL"]


def test_parse_resume_pdf(tmp_path):
    pdf_path = tmp_path / "r.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "姓名：张三", fontname="china-s")
    doc.save(str(pdf_path))
    doc.close()

    raw, structured = parse_resume_pdf(str(pdf_path), FakeLLM(RESUME_DATA))
    assert "张三" in raw
    assert structured["name"] == "张三"
