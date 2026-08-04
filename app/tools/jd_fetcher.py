import re

import httpx


def fetch_url_text(url: str, timeout: float = 15.0) -> str:
    """抓取公开网页文本并做粗粒度清理（去 script/style/标签）。"""
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    text = response.text
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()
