import json

from app.eval.golden import sync_golden_set
from app.models import EvalCase


def test_sync_golden_set_idempotent(db_session, tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(
        json.dumps(
            [
                {
                    "title": "case-1",
                    "task_type": "match",
                    "input": {"resume_id": "r1", "jd_id": "j1"},
                    "expected": {"total_min": 70, "total_max": 95},
                },
                {
                    "title": "case-1",
                    "task_type": "match",
                    "input": {"resume_id": "r1", "jd_id": "j1"},
                    "expected": {"total_min": 75, "total_max": 95},
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    first = sync_golden_set(db_session, str(path))
    assert first["added"] == 1
    assert first["updated"] == 1
    assert db_session.query(EvalCase).count() == 1
    case = db_session.query(EvalCase).one()
    assert case.expected_json["total_min"] == 75


def test_sync_golden_set_empty_file(db_session, tmp_path):
    path = tmp_path / "golden.json"
    path.write_text("[]", encoding="utf-8")
    result = sync_golden_set(db_session, str(path))
    assert result == {"added": 0, "updated": 0, "deleted": 0, "total": 0}


def test_sync_golden_set_removes_stale_cases(db_session, tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(
        json.dumps(
            [{"title": "old-case", "task_type": "match", "input": {}, "expected": {}}]
        ),
        encoding="utf-8",
    )
    sync_golden_set(db_session, str(path))
    path.write_text(
        json.dumps(
            [{"title": "new-case", "task_type": "match", "input": {}, "expected": {}}]
        ),
        encoding="utf-8",
    )
    result = sync_golden_set(db_session, str(path))
    assert result["added"] == 1
    assert result["deleted"] == 1
    titles = {c.title for c in db_session.query(EvalCase).all()}
    assert titles == {"new-case"}
