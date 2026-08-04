import hashlib
from typing import Any

import chromadb

from app.config import settings

COLLECTION_RESUMES = "resumes"
COLLECTION_JDS = "jds"


class HashEmbeddingFunction(chromadb.EmbeddingFunction):
    """确定性离线嵌入：token 哈希到 128 维向量，无需联网下载模型。"""

    def __init__(self) -> None:
        pass

    def __call__(self, input):
        vecs = []
        for doc in input:
            vec = [0.0] * 128
            for token in doc.split():
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                vec[int(digest, 16) % 128] += 1.0
            vecs.append(vec)
        return vecs

    @staticmethod
    def name() -> str:
        return "job_copilot_hash"

    def get_config(self) -> dict:
        return {}

    @classmethod
    def build_from_config(cls, config: dict) -> "HashEmbeddingFunction":
        return cls()


class VectorStore:
    """ChromaDB 封装：文档写入与向量检索。"""

    def __init__(
        self,
        path: str | None = None,
        client: Any | None = None,
        embedding_function: Any | None = None,
    ):
        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(path=path or settings.chroma_path)
        self._embedding_function = embedding_function or HashEmbeddingFunction()
        self._collections: dict[str, Any] = {}

    def _collection(self, name: str):
        if name not in self._collections:
            kwargs = {}
            if self._embedding_function is not None:
                kwargs["embedding_function"] = self._embedding_function
            self._collections[name] = self._client.get_or_create_collection(name, **kwargs)
        return self._collections[name]

    def add(
        self,
        collection: str,
        docs: list[str],
        ids: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        self._collection(collection).upsert(
            documents=docs,
            ids=ids,
            metadatas=metadatas or [{}] * len(docs),
        )

    def query(self, collection: str, query_texts: list[str], top_k: int = 5) -> list[dict]:
        result = self._collection(collection).query(query_texts=query_texts, n_results=top_k)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0] or [{}] * len(docs)
        ids = result.get("ids", [[]])[0]
        return [
            {"id": ids[i], "text": docs[i], "metadata": metas[i]}
            for i in range(len(docs))
        ]
