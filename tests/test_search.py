from app.tools.search import SearchTool


FAKE_DDG_HTML = (
    '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fjob">'
    "京东 招聘 Python 实习生</a>"
    '<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fjob">'
    "两轮技术面</a>"
)


def test_search_duckduckgo_fallback_without_key(monkeypatch):
    class FakeResponse:
        text = FAKE_DDG_HTML

        def raise_for_status(self):
            pass

    monkeypatch.setattr("httpx.get", lambda *a, **k: FakeResponse())
    tool = SearchTool(api_key="")
    results = tool.search("京东 面试", top_k=5)
    assert results[0]["title"] == "京东 招聘 Python 实习生"
    assert results[0]["url"] == "https://example.com/job"
    assert results[0]["content"] == "两轮技术面"


def test_search_tavily(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [
                    {"title": "京东面试攻略", "url": "https://example.com", "content": "两轮技术面"}
                ]
            }

    monkeypatch.setattr("httpx.post", lambda *a, **k: FakeResponse())
    tool = SearchTool(api_key="fake-key")
    results = tool.search("京东 面试", top_k=5)
    assert results[0]["title"] == "京东面试攻略"
    assert results[0]["url"] == "https://example.com"
