from app.schemas import JDStructured, ResumeStructured


def test_resume_schema_accepts_sample():
    data = {
        "name": "张三",
        "email": "a@b.com",
        "phone": "13800000000",
        "city": "北京",
        "education": [
            {"school": "XX 大学", "degree": "硕士", "major": "计算机", "years": "2024-2027"}
        ],
        "experience": [],
        "projects": [],
        "skills": ["Python", "LangGraph"],
    }
    resume = ResumeStructured.model_validate(data)
    assert resume.skills == ["Python", "LangGraph"]
    assert resume.education[0].major == "计算机"


def test_jd_schema_defaults():
    jd = JDStructured.model_validate({})
    assert jd.requirements == []
    assert jd.company == ""
