from app.models import JD
from app.services.insight_service import generate_market_insight, parse_salary


def test_parse_salary():
    assert parse_salary("20-40K·14薪") == (20.0, 40.0)
    assert parse_salary("2-4万·14薪") == (20.0, 40.0)
    assert parse_salary("面议") is None
    assert parse_salary("") is None


def test_generate_market_insight(db_session):
    jd1 = JD(
        company="京东",
        title="A",
        raw_text="a",
        structured_json={
            "requirements": ["Python LangGraph"],
            "location": "北京",
            "salary": "20-40K·14薪",
        },
    )
    jd2 = JD(
        company="字节",
        title="B",
        raw_text="b",
        structured_json={
            "requirements": ["Python RAG"],
            "location": "上海",
            "salary": "30-50K·15薪",
        },
    )
    db_session.add_all([jd1, jd2])
    db_session.commit()

    report = generate_market_insight(db_session)
    assert report["total_jds"] == 2
    assert report["top_skills"][0]["skill"] == "Python"
    assert report["top_skills"][0]["count"] == 2
    assert report["salary_stats"]["median"] == 45.0
    assert report["location_counts"]["北京"] == 1
    assert report["company_counts"]["京东"] == 1
    assert report["generated_at"]
