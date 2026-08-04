from pydantic import BaseModel


class Education(BaseModel):
    school: str = ""
    degree: str = ""
    major: str = ""
    years: str = ""


class Experience(BaseModel):
    company: str = ""
    role: str = ""
    years: str = ""
    highlights: list[str] = []


class Project(BaseModel):
    name: str = ""
    description: str = ""
    tech: list[str] = []
    highlights: list[str] = []


class ResumeStructured(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    education: list[Education] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    skills: list[str] = []


class JDStructured(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    salary: str = ""
    responsibilities: list[str] = []
    requirements: list[str] = []


class MatchRequest(BaseModel):
    resume_id: str
    jd_ids: list[str]


class DimensionScores(BaseModel):
    skill_match: float = 0.0
    experience_match: float = 0.0
    education_match: float = 0.0
    hard_requirements: float = 0.0


class MatchResult(BaseModel):
    match_id: str = ""
    jd_id: str = ""
    dimension_scores: DimensionScores = DimensionScores()
    reasons: dict[str, str] = {}
    total_score: float = 0.0
    gaps: list[str] = []
    summary: str = ""


class CoverLetterRequest(BaseModel):
    match_id: str
    tone: str = "standard"
