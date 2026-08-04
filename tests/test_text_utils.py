from app.utils.text import extract_terms


def test_extract_terms_basic():
    assert extract_terms("Python, LangGraph 与 MySQL") == {"Python", "LangGraph", "MySQL"}


def test_extract_terms_empty():
    assert extract_terms("") == set()


def test_extract_terms_ignores_cjk_only():
    assert extract_terms("招聘实习生") == set()
