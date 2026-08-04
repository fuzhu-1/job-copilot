from app.agents.supervisor import classify_intent, handle_message


class FakeLLMIntent:
    def __init__(self, data):
        self.data = data

    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(self.data).model_dump()


def test_classify_intent():
    llm = FakeLLMIntent({"intent": "market_insight", "target": ""})
    result = classify_intent("分析近期岗位趋势", llm)
    assert result["intent"] == "market_insight"


def test_classify_help_intent():
    llm = FakeLLMIntent({"intent": "help", "target": ""})
    result = classify_intent("你好", llm)
    assert result["intent"] == "help"


def test_handle_message_guidance_for_jd():
    llm = FakeLLMIntent({"intent": "jd_add", "target": ""})
    result = handle_message(None, "帮我加一条 JD", llm)
    assert result["intent"] == "jd_add"
    assert "粘贴" in result["message"]


def test_handle_message_market_insight(db_session):
    llm = FakeLLMIntent({"intent": "market_insight", "target": ""})
    result = handle_message(db_session, "分析趋势", llm)
    assert result["intent"] == "market_insight"
    assert result["payload"]["report"]["total_jds"] == 0
