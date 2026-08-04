from app.tools.jd_fetcher import fetch_url_text


def test_fetch_url_text_strips_script(monkeypatch):
    class FakeResponse:
        text = "<html><script>bad()</script><body>招聘 AI 产品实习生</body></html>"

        def raise_for_status(self):
            pass

    captured = {}

    def fake_get(*a, **k):
        captured.update(k)
        return FakeResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    text = fetch_url_text("https://example.com/jd")
    assert "招聘 AI 产品实习生" in text
    assert "bad()" not in text
    assert "User-Agent" in captured.get("headers", {})
    assert "Mozilla" in captured["headers"]["User-Agent"]
