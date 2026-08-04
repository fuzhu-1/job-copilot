import re


def extract_terms(text: str) -> set[str]:
    """提取 ASCII 技能词（Python/LangGraph/MySQL 等）。中文语义由 LLM 层处理。"""
    return set(re.findall(r"[A-Za-z0-9][A-Za-z0-9+#._-]{1,}", text))
