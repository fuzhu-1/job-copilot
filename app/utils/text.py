import re

import jieba

_ASCII_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#._-]{1,}")
_HAS_TEXT_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")


def extract_terms(text: str) -> set[str]:
    """提取技能词：ASCII 词 + jieba 中文分词（双字及以上）。"""
    terms: set[str] = set()
    terms.update(_ASCII_RE.findall(text))
    for word in jieba.cut(text):
        word = word.strip()
        if len(word) >= 2 and _HAS_TEXT_RE.search(word):
            terms.add(word)
    return terms
