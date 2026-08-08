"""生成可移植的评测样例数据与 golden set。

用法: python scripts/seed_eval_data.py

用确定性 UUID 保证任何环境跑出相同的 ID，golden_set.json 才能跨环境复用。
"""

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import JD, Match, Resume  # noqa: E402


def fixed_id(key: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"job-copilot-eval/{key}").hex


RESUMES = {
    "resume-backend": {
        "name": "张三",
        "email": "zhangsan@example.com",
        "phone": "13800000000",
        "city": "北京",
        "education": [
            {"school": "XX 大学", "degree": "硕士", "major": "计算机科学与技术", "years": "2024-2027"}
        ],
        "experience": [
            {
                "company": "某科技公司",
                "role": "后端开发实习生",
                "years": "2025-06 至 2025-09",
                "highlights": ["实现 RAG 检索服务，QPS 提升 40%"],
            }
        ],
        "projects": [
            {
                "name": "DeepResearch-Agent",
                "description": "多 Agent 研究系统",
                "tech": ["LangGraph", "FastAPI"],
                "highlights": ["Planner-Researcher-Writer-Reviewer 四 Agent 协作"],
            }
        ],
        "skills": ["Python", "LangGraph", "FastAPI", "RAG", "SQL"],
    },
}

JDS = {
    "jd-llm-dev": {
        "company": "京东",
        "title": "LLM 应用开发实习生",
        "location": "北京",
        "salary": "面议",
        "responsibilities": ["参与 Agent 功能开发", "维护 RAG 检索链路"],
        "requirements": ["熟悉 Python", "了解 LangGraph 或类似编排框架", "有 RAG 项目经验优先"],
    },
    "jd-backend": {
        "company": "腾讯",
        "title": "后端开发实习生",
        "location": "深圳",
        "salary": "20-40K·14薪",
        "responsibilities": ["负责服务端接口开发", "参与系统性能优化"],
        "requirements": ["熟悉 Python/Go", "了解 MySQL 与 Redis", "有高并发项目经验加分"],
    },
}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        resume_ids = {}
        for key, data in RESUMES.items():
            rid = fixed_id(key)
            db.merge(
                Resume(
                    id=rid,
                    source_type="seed",
                    raw_text=json.dumps(data, ensure_ascii=False),
                    structured_json=data,
                    status="confirmed",
                )
            )
            resume_ids[key] = rid
        jd_ids = {}
        for key, data in JDS.items():
            jid = fixed_id(key)
            db.merge(
                JD(
                    id=jid,
                    source_type="seed",
                    company=data["company"],
                    title=data["title"],
                    raw_text=json.dumps(data, ensure_ascii=False),
                    structured_json=data,
                )
            )
            jd_ids[key] = jid
        db.flush()  # 先落库简历/JD，保证 match 外键可满足
        match = db.merge(
            Match(
                id=fixed_id("match-llm"),
                resume_id=resume_ids["resume-backend"],
                jd_id=jd_ids["jd-llm-dev"],
                total_score=75.0,
            )
        )
        db.commit()
        match_id = match.id
    finally:
        db.close()

    golden = [
        {
            "title": "match-1-后端简历 vs LLM 开发岗",
            "task_type": "match",
            "input": {"resume_id": resume_ids["resume-backend"], "jd_id": jd_ids["jd-llm-dev"]},
            "expected": {"total_min": 40, "total_max": 95},
        },
        {
            "title": "match-2-后端简历 vs 后端岗",
            "task_type": "match",
            "input": {"resume_id": resume_ids["resume-backend"], "jd_id": jd_ids["jd-backend"]},
            "expected": {"total_min": 50, "total_max": 95},
        },
        {
            "title": "cover-letter-llm",
            "task_type": "cover_letter",
            "input": {"match_id": match_id},
            "expected": {"keywords": ["Agent"], "min_score": 0.5},
        },
    ]
    out = ROOT / "data" / "golden_set.json"
    out.write_text(json.dumps(golden, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"seeded {len(RESUMES)} resumes, {len(JDS)} jds, 1 match -> {out}")


if __name__ == "__main__":
    main()
