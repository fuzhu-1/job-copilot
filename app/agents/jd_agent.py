from app.llm import LLMService
from app.schemas import JDStructured


def structure_jd_text(text: str, llm: LLMService | None = None) -> dict:
    """将 JD 文本结构化为 JDStructured。"""
    llm = llm or LLMService()
    messages = [
        {
            "role": "system",
            "content": "你是招聘信息结构化专家。请把岗位 JD 提取为结构化 JSON，缺失字段留空。",
        },
        {"role": "user", "content": text[:20000]},
    ]
    return llm.complete_structured(messages, JDStructured)
