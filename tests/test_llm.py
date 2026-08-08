import json

from app.llm import LLMService
from app.schemas import ResumeStructured


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _FakeCompletions:
    def __init__(self, contents):
        self._contents = contents
        self.calls = 0

    def create(self, **kwargs):
        content = self._contents[min(self.calls, len(self._contents) - 1)]
        self.calls += 1
        return _Response(content)


class _FakeChat:
    def __init__(self, contents):
        self.completions = _FakeCompletions(contents)


class FakeClient:
    def __init__(self, contents):
        self.chat = _FakeChat(contents)


def test_complete_returns_text():
    client = FakeClient(["hello"])
    svc = LLMService(client=client)
    assert svc.complete([{"role": "user", "content": "hi"}]) == "hello"


def test_complete_structured_parses_fenced_json():
    payload = json.dumps({"name": "张三", "skills": ["Python"]}, ensure_ascii=False)
    client = FakeClient([f"```json\n{payload}\n```"])
    svc = LLMService(client=client)
    result = svc.complete_structured([{"role": "user", "content": "x"}], ResumeStructured)
    assert result["name"] == "张三"
    assert result["skills"] == ["Python"]


def test_complete_structured_retries_on_invalid_json():
    payload = json.dumps({"name": "李四"}, ensure_ascii=False)
    client = FakeClient(["not json", payload])
    svc = LLMService(client=client)
    result = svc.complete_structured([{"role": "user", "content": "x"}], ResumeStructured)
    assert result["name"] == "李四"
    assert client.chat.completions.calls == 2


class _RaisingCompletions:
    def __init__(self, fail_count=1):
        self.fail_count = fail_count
        self.calls = 0
        self._ok = _FakeCompletions(["ok"])

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_count:
            exc = RuntimeError("rate limited")
            exc.status_code = 429
            raise exc
        return self._ok.create(**kwargs)


class FakeRaisingClient:
    def __init__(self):
        class _Chat:
            def __init__(self):
                self.completions = _RaisingCompletions()

        self.chat = _Chat()


def test_complete_retries_on_429():
    client = FakeRaisingClient()
    svc = LLMService(client=client, max_retries=2)
    assert svc.complete([{"role": "user", "content": "hi"}]) == "ok"
    assert client.chat.completions.calls == 2


class _JsonModeRejectCompletions:
    def __init__(self):
        self._ok = _FakeCompletions(['{"name": "王五"}'])
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("response_format"):
            exc = RuntimeError("unsupported")
            exc.status_code = 400
            raise exc
        return self._ok.create(**kwargs)


class FakeJsonRejectClient:
    def __init__(self):
        class _Chat:
            def __init__(self):
                self.completions = _JsonModeRejectCompletions()

        self.chat = _Chat()


def test_complete_structured_falls_back_without_json_mode():
    client = FakeJsonRejectClient()
    svc = LLMService(client=client, max_retries=0)
    result = svc.complete_structured([{"role": "user", "content": "x"}], ResumeStructured)
    assert result["name"] == "王五"
    assert client.chat.completions.calls[0].get("response_format") is not None
    assert "response_format" not in client.chat.completions.calls[-1]
