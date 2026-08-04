import json

from sqlalchemy.orm import Session

from app.models import EvalCase


def sync_golden_set(db: Session, path: str) -> dict:
    """从 JSON 文件同步 golden set 到 EvalCase 表（按 title 幂等 upsert，文件为准，清理已移除用例）。"""
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    existing = {c.title: c for c in db.query(EvalCase).all()}
    pending: dict[str, EvalCase] = {}
    added = 0
    updated = 0
    titles = set()
    for item in cases:
        title = item["title"]
        titles.add(title)
        case = existing.get(title) or pending.get(title)
        if case is None:
            case = EvalCase(
                title=title,
                task_type=item["task_type"],
                input_json=item["input"],
                expected_json=item["expected"],
            )
            db.add(case)
            pending[title] = case
            added += 1
        else:
            case.task_type = item["task_type"]
            case.input_json = item["input"]
            case.expected_json = item["expected"]
            updated += 1
    deleted = 0
    for title, case in existing.items():
        if title not in titles:
            db.delete(case)
            deleted += 1
    db.commit()
    return {"added": added, "updated": updated, "deleted": deleted, "total": len(cases)}
