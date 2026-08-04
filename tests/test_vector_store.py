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
