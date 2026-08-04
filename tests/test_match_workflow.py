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
