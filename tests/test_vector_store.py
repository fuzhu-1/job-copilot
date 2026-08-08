from app.vector_store import COLLECTION_RESUMES


def test_add_and_query(vector_store):
    vector_store.add(
        COLLECTION_RESUMES,
        ["我会 Python 和 LangGraph", "我会 Java 和 Spring"],
        ["r1", "r2"],
        [{"resume_id": "r1"}, {"resume_id": "r2"}],
    )
    results = vector_store.query(COLLECTION_RESUMES, ["Python LangGraph"], top_k=1)
    assert results[0]["id"] == "r1"
    assert results[0]["metadata"]["resume_id"] == "r1"


def test_query_chinese_doc(vector_store):
    vector_store.add(
        COLLECTION_RESUMES,
        ["熟悉机器学习与 RAG 检索", "熟悉 Java 与 Spring"],
        ["r1", "r2"],
        [{"resume_id": "r1"}, {"resume_id": "r2"}],
    )
    results = vector_store.query(COLLECTION_RESUMES, ["机器学习"], top_k=1)
    assert results[0]["id"] == "r1"
    assert results[0]["text"] == "熟悉机器学习与 RAG 检索"


def test_delete_removes_doc(vector_store):
    vector_store.add(COLLECTION_RESUMES, ["Python"], ["r1"], [{"resume_id": "r1"}])
    vector_store.delete(COLLECTION_RESUMES, ["r1"])
    assert vector_store.query(COLLECTION_RESUMES, ["Python"], top_k=5) == []
