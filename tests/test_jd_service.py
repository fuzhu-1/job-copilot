from app.services.jd_service import create_jd_from_text, create_jd_from_url
from fixtures_data import JD_DATA


class FakeLLM:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def test_create_jd_from_text(db_session, vector_store):
    jd = create_jd_from_text(
        db_session, "京东招聘 LLM 应用开发实习生", vector_store, llm=FakeLLM(JD_DATA)
    )
    assert jd.company == "京东"
    assert jd.title == "LLM 应用开发实习生"
    hits = vector_store.query("jds", ["LLM"], top_k=1)
    assert hits[0]["id"] == jd.id


def test_create_jd_from_url(db_session, vector_store, monkeypatch):
    class FakeResponse:
        text = "<html><body>岗位名称：AI 产品实习生</body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("httpx.get", lambda *a, **k: FakeResponse())
    jd = create_jd_from_url(
        db_session, "https://example.com/jd", vector_store, llm=FakeLLM(JD_DATA)
    )
    assert jd.source_type == "url"
    assert jd.source_url == "https://example.com/jd"
