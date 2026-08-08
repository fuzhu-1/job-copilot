import json
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jieba

from app.config import settings

COLLECTION_RESUMES = "resumes"
COLLECTION_JDS = "jds"

_ASCII_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#._-]{1,}")
_HAS_TEXT_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(t.lower() for t in _ASCII_RE.findall(text))
    for word in jieba.cut(text):
        word = word.strip().lower()
        if len(word) >= 2 and _HAS_TEXT_RE.search(word):
            tokens.append(word)
    return tokens


class VectorStore:
    """轻量中文检索：jieba 分词 + BM25 打分，SQLite 持久化文档。

    接口与旧 ChromaDB 版本保持兼容（add/query/delete），调用方无需改动。
    """

    def __init__(self, path: str | None = None):
        self._db_path = Path(path or settings.search_db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS search_docs ("
            " collection TEXT NOT NULL,"
            " doc_id TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " metadata_json TEXT NOT NULL DEFAULT '{}',"
            " updated_at TEXT NOT NULL,"
            " PRIMARY KEY (collection, doc_id)"
            ")"
        )
        self._conn.commit()
        self._documents: dict[str, list[dict[str, Any]]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        rows = self._conn.execute(
            "SELECT collection, doc_id, content, metadata_json FROM search_docs"
        ).fetchall()
        for collection, doc_id, content, metadata_json in rows:
            self._documents.setdefault(collection, []).append(
                {"id": doc_id, "text": content, "metadata": json.loads(metadata_json)}
            )
        self._loaded = True

    def add(
        self,
        collection: str,
        docs: list[str],
        ids: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        self._ensure_loaded()
        now = datetime.now(timezone.utc).isoformat()
        metas = metadatas or [{}] * len(docs)
        for doc, doc_id, meta in zip(docs, ids, metas):
            self._conn.execute(
                "INSERT INTO search_docs "
                "(collection, doc_id, content, metadata_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(collection, doc_id) DO UPDATE SET "
                " content=excluded.content, metadata_json=excluded.metadata_json,"
                " updated_at=excluded.updated_at",
                (collection, doc_id, doc, json.dumps(meta, ensure_ascii=False), now),
            )
            bucket = self._documents.setdefault(collection, [])
            entry = {"id": doc_id, "text": doc, "metadata": meta}
            for i, existing in enumerate(bucket):
                if existing["id"] == doc_id:
                    bucket[i] = entry
                    break
            else:
                bucket.append(entry)
        self._conn.commit()

    def delete(self, collection: str, ids: list[str]) -> None:
        self._ensure_loaded()
        removed = set(ids)
        self._documents[collection] = [
            d for d in self._documents.get(collection, []) if d["id"] not in removed
        ]
        for doc_id in ids:
            self._conn.execute(
                "DELETE FROM search_docs WHERE collection = ? AND doc_id = ?",
                (collection, doc_id),
            )
        self._conn.commit()

    def query(self, collection: str, query_texts: list[str], top_k: int = 5) -> list[dict]:
        self._ensure_loaded()
        docs = self._documents.get(collection, [])
        if not docs:
            return []
        query_tokens = _tokenize(query_texts[0])
        if not query_tokens:
            return []
        doc_tokens = [_tokenize(d["text"]) for d in docs]
        avg_len = sum(len(t) for t in doc_tokens) / len(doc_tokens)
        df = Counter(tok for tokens in doc_tokens for tok in set(tokens))
        n = len(docs)
        scored: list[tuple[float, dict[str, Any]]] = []
        for doc, tokens in zip(docs, doc_tokens):
            freq = Counter(tokens)
            dl = len(tokens)
            score = 0.0
            for qt in query_tokens:
                tf = freq.get(qt, 0)
                if tf == 0:
                    continue
                idf = math.log(1 + (n - df[qt] + 0.5) / (df[qt] + 0.5))
                score += idf * (tf * 2.5) / (tf + 1.5 * (1 - 0.75 + 0.75 * dl / avg_len))
            scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for score, doc in scored[:top_k] if score > 0]
