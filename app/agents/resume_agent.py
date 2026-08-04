from app.llm import LLMService
from app.schemas import ResumeStructured
from app.tools.pdf_parser import extract_pdf_text


def parse_resume_text(raw_text: str, llm: LLMService | None = None) -> dict:
    """将简历文本结构化为 ResumeStructured。"""
    llm = llm or LLMService()
    messages = [
        {
            "role": "system",
            "content": "你是资深 HR 简历分析师。请把简历内容提取为结构化 JSON，缺失字段留空。",
        },
        {"role": "user", "content": raw_text[:20000]},
    ]
    return llm.complete_structured(messages, ResumeStructured)


def parse_resume_pdf(path: str, llm: LLMService | None = None) -> tuple[str, dict]:
    """解析 PDF 文件，返回 (原始文本, 结构化结果)。"""
    raw_text = extract_pdf_text(path)
    structured = parse_resume_text(raw_text, llm)
    return raw_text, structured
