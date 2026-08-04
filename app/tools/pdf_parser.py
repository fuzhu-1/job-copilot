import fitz


def extract_pdf_text(path: str) -> str:
    """从 PDF 提取全文；空页返回空字符串。"""
    doc = fitz.open(path)
    try:
        parts = [page.get_text() for page in doc]
    finally:
        doc.close()
    return "\n".join(parts).strip()
