import fitz

from app.models import Resume
from app.services.resume_service import confirm_resume, create_resume_from_file
from fixtures_data import RESUME_DATA


class FakeLLM:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def _make_pdf(tmp_path):
    path = tmp_path / "r.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "姓名：张三 技能：Python LangGraph", fontname="china-s")
    doc.save(str(path))
    doc.close()
    return str(path)


def test_create_then_confirm_resume(db_session, vector_store, tmp_path):
    resume = create_resume_from_file(
        db_session, _make_pdf(tmp_path), vector_store, llm=FakeLLM(RESUME_DATA)
    )
    assert resume.status == "pending_confirmation"
    assert resume.structured_json["name"] == "张三"

    confirmed = confirm_resume(db_session, resume.id, resume.structured_json, vector_store)
    assert confirmed.status == "confirmed"

    hits = vector_store.query("resumes", ["Python LangGraph"], top_k=1)
    assert hits[0]["id"] == resume.id
