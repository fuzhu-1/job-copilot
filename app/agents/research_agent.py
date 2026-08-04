from app.llm import LLMService
from app.schemas import CompanyReport


def generate_report(
    company: str,
    title: str,
    jd_summary: str,
    snippets: list[dict],
    llm: LLMService,
) -> dict:
    """基于公司/JD/搜索片段生成企业研究报告。"""
    source_note = ""
    if not snippets:
        source_note = "未获取到搜索结果，报告基于模型知识生成，仅供参考"
    snippet_text = "\n".join(
        f"- {s.get('title', '')}: {s.get('content', '')[:200]}" for s in snippets[:5]
    )
    messages = [
        {
            "role": "system",
            "content": "你是求职情报分析师。基于已知信息生成企业研究报告，缺失信息如实说明，不要编造。",
        },
        {
            "role": "user",
            "content": (
                f"公司：{company}\n岗位：{title}\nJD 摘要：{jd_summary}\n"
                f"搜索片段：\n{snippet_text or '（无）'}\n"
                "输出 JSON：company(公司名)、business_lines(业务线)、interview_process(面试流程)、"
                "salary_reference(薪资参考)、team_background(团队背景)、tips(求职建议，最多 3 条)、"
                f"source_note(信息源说明，此处填：{source_note})"
            ),
        },
    ]
    data = llm.complete_structured(messages, CompanyReport)
    if not data["source_note"]:
        data["source_note"] = source_note
    return data
