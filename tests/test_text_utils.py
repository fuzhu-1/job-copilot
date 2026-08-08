from app.utils.text import extract_terms


def test_extract_terms_basic():
    assert extract_terms("Python, LangGraph 与 MySQL") == {"Python", "LangGraph", "MySQL"}


def test_extract_terms_empty():
    assert extract_terms("") == set()


def test_extract_terms_extracts_chinese_words():
    assert extract_terms("招聘实习生") == {"招聘", "实习生"}


def test_extract_terms_chinese():
    terms = extract_terms("熟悉 Python，有机器学习项目经验，掌握 MySQL")
    assert "机器" in terms
    assert "学习" in terms
    assert "项目" in terms
    assert "经验" in terms
    assert "的" not in terms  # 单字虚词被过滤
    assert "Python" in terms
    assert "MySQL" in terms
