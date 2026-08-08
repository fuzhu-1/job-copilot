from app.workflow.graph import _extract_terms, build_match_graph


class FakeLLM:
    def complete_structured(self, messages, schema, max_tokens=2000):
        return schema.model_validate(
            {
                "skill_match": 90.0,
                "experience_match": 80.0,
                "education_match": 70.0,
                "hard_requirements": 85.0,
                "reasons": {"skill_match": "技能重合度高"},
                "gaps": ["缺少企业级项目经验", "缺少企业级项目经验"],
                "summary": "整体匹配",
            }
        ).model_dump()


def test_match_graph_full_flow():
    graph = build_match_graph(FakeLLM())
    state = {
        "resume_text": '{"skills": ["Python", "LangGraph"]}',
        "jd_text": '{"requirements": ["Python"]}',
    }
    result = graph.invoke(state)
    assert result["total_score"] == 83.0  # 90*0.35 + 80*0.3 + 70*0.15 + 85*0.2
    assert result["gaps"] == ["缺少企业级项目经验"]  # 去重
    assert result["dimension_scores"]["skill_match"] == 90.0
    assert result["summary"] == "整体匹配"


def test_extract_terms():
    assert _extract_terms("Python, LangGraph 与 MySQL") == {"Python", "LangGraph", "MySQL"}


def test_extract_terms_chinese_overlap():
    resume = '{"skills": ["机器学习", "RAG"], "projects": [{"name": "检索系统"}]}'
    jd = '{"requirements": ["熟悉机器学习", "有 RAG 经验"]}'
    overlap = len(_extract_terms(resume) & _extract_terms(jd)) / len(_extract_terms(jd))
    assert overlap > 0.3  # 中文+ASCII 都能命中，重叠率应显著大于 0


def test_default_graph_is_cached():
    import app.workflow.graph as graph_module

    first = build_match_graph(None)
    assert graph_module._default_graph is not None
    assert build_match_graph(None) is first


class ZeroThenScoreLLM:
    def __init__(self):
        self.calls = 0

    def complete_structured(self, messages, schema, max_tokens=2000):
        self.calls += 1
        if self.calls == 1:
            return schema.model_validate({}).model_dump()
        return schema.model_validate(
            {
                "skill_match": 90.0,
                "experience_match": 80.0,
                "education_match": 70.0,
                "hard_requirements": 85.0,
                "reasons": {"skill_match": "技能重合度高"},
                "gaps": ["缺少企业级项目经验"],
                "summary": "整体匹配",
            }
        ).model_dump()


def test_match_graph_retries_when_scores_all_zero():
    llm = ZeroThenScoreLLM()
    graph = build_match_graph(llm)
    state = {
        "resume_text": '{"skills": ["Python", "LangGraph"]}',
        "jd_text": '{"requirements": ["Python"]}',
    }
    result = graph.invoke(state)
    assert result["total_score"] == 83.0
    assert llm.calls == 2
