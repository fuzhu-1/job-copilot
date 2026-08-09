from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.utils.text import extract_terms


class MatchState(TypedDict, total=False):
    resume_text: str
    jd_text: str
    keyword_overlap: float
    dimension_scores: dict
    reasons: dict
    total_score: float
    gaps: list
    summary: str


class MatchScoring(BaseModel):
    skill_match: float = 0.0
    experience_match: float = 0.0
    education_match: float = 0.0
    hard_requirements: float = 0.0
    reasons: dict[str, str] = {}
    gaps: list[str] = []
    summary: str = ""


WEIGHTS = {
    "skill_match": 0.35,
    "experience_match": 0.30,
    "education_match": 0.15,
    "hard_requirements": 0.20,
}


def _extract_terms(text: str) -> set[str]:
    """兼容别名：真实实现见 app/utils/text.py。"""
    return extract_terms(text)


_default_graph = None


def build_match_graph(llm=None):
    if llm is None:
        global _default_graph
        if _default_graph is None:
            from app.llm import LLMService

            _default_graph = _build(LLMService())
        return _default_graph
    return _build(llm)


def _build(llm):
    def rule_node(state: MatchState) -> MatchState:
        resume_terms = _extract_terms(state["resume_text"])
        jd_terms = _extract_terms(state["jd_text"])
        overlap = round(len(resume_terms & jd_terms) / max(len(jd_terms), 1), 2)
        return {"keyword_overlap": overlap}

    def score_node(state: MatchState) -> MatchState:
        prompt = (
            "你是资深招聘匹配专家。根据简历和 JD 判断匹配度，输出 JSON。\n"
            f"简历：{state['resume_text'][:8000]}\n"
            f"JD：{state['jd_text'][:8000]}\n"
            f"规则层关键词重叠率：{state.get('keyword_overlap', 0)}\n"
            "必须输出顶层 JSON 字段（不要嵌套 dimensions，不要多余字段），格式：\n"
            '{"skill_match": 0-100, "experience_match": 0-100, "education_match": 0-100, '
            '"hard_requirements": 0-100, "reasons": {"skill_match": "理由"}, '
            '"gaps": ["中文差距建议，最多3条"], "summary": "一句话总结"}\n'
            "评分维度说明：skill_match(技能匹配)/experience_match(经历相关)/"
            "education_match(教育背景)/hard_requirements(硬性条件)，每项 0-100。"
        )
        messages = [{"role": "user", "content": prompt}]
        data = llm.complete_structured(messages, MatchScoring)
        for _ in range(2):
            if not all(data[k] == 0 for k in WEIGHTS):
                break
            data = llm.complete_structured(
                messages
                + [
                    {
                        "role": "user",
                        "content": (
                            "上一次输出所有评分维度均为 0。请重新评估，并确保输出顶层 "
                            "skill_match/experience_match/education_match/hard_requirements "
                            "四个 0-100 数值字段（不要嵌套、不要省略）。"
                        ),
                    }
                ],
                MatchScoring,
            )
        total = round(sum(data[k] * WEIGHTS[k] for k in WEIGHTS), 1)
        return {
            "dimension_scores": {k: data[k] for k in WEIGHTS},
            "reasons": data["reasons"],
            "total_score": total,
            "gaps": data["gaps"],
            "summary": data["summary"],
        }

    def gap_node(state: MatchState) -> MatchState:
        gaps = list(dict.fromkeys(state.get("gaps", [])))[:3]
        return {"gaps": gaps}

    graph = StateGraph(MatchState)
    graph.add_node("rule", rule_node)
    graph.add_node("score", score_node)
    graph.add_node("gaps", gap_node)
    graph.add_edge(START, "rule")
    graph.add_edge("rule", "score")
    graph.add_edge("score", "gaps")
    graph.add_edge("gaps", END)
    return graph.compile()
