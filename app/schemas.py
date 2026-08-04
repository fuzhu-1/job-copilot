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


class ApplicationCreate(BaseModel):
    match_id: str
    notes: str = ""


class ApplicationTransition(BaseModel):
    target_status: str
    note: str = ""


class CustomStatusCreate(BaseModel):
    status: str
    from_status: str = "applied"
    next: list[str] = []


class CompanyReport(BaseModel):
    company: str = ""
    business_lines: list[str] = []
    interview_process: str = ""
    salary_reference: str = ""
    team_background: str = ""
    tips: list[str] = []
    source_note: str = ""


class Intent(BaseModel):
    intent: str = "help"
    target: str = ""


class AgentMessage(BaseModel):
    message: str


class InterviewCreate(BaseModel):
    jd_id: str
    resume_id: str


class InterviewRespond(BaseModel):
    answer: str


class AnswerEvaluation(BaseModel):
    score: float = 0.0
    feedback: str = ""
    next_question: str = ""


class InterviewSummary(BaseModel):
    overall_score: float = 0.0
    strengths: list[str] = []
    weaknesses: list[str] = []
    improvement_plan: list[str] = []
