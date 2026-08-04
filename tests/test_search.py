from app.tools.search import SearchTool


def test_search_no_key_returns_empty():
    tool = SearchTool(api_key="")
    assert tool.search("京东 面试") == []


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
