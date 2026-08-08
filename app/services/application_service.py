from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Application, JD, Match, jd_display_name

CORE_STATUSES = ["applied", "screening", "interview", "offer", "accepted", "rejected"]

DEFAULT_TRANSITIONS = {
    "applied": ["screening", "interview", "rejected"],
    "screening": ["interview", "applied", "rejected"],
    "interview": ["offer", "screening", "rejected"],
    "offer": ["accepted", "interview", "rejected"],
    "accepted": [],
    "rejected": ["applied"],
}

REMINDER_THRESHOLD_DAYS = {"applied": 3, "screening": 7, "interview": 5, "offer": 2}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_application(db: Session, match_id: str, notes: str = "") -> Application:
    match = db.get(Match, match_id)
    if match is None:
        raise KeyError(f"match not found: {match_id}")
    application = Application(
        match_id=match_id,
        current_status="applied",
        status_history_json=[{"status": "applied", "at": _now().isoformat()}],
        notes=notes,
    )
    db.add(application)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("该岗位已创建投递记录") from None
    db.refresh(application)
    return application


def allowed_next(application: Application) -> list[str]:
    custom = application.custom_statuses_json.get(application.current_status, [])
    nexts = set(DEFAULT_TRANSITIONS.get(application.current_status, [])) | set(custom)
    nexts.discard(application.current_status)  # 不允许原地停留（防自环）
    return sorted(nexts)


def transition(db: Session, app_id: str, target_status: str, note: str = "") -> Application:
    application = db.get(Application, app_id)
    if application is None:
        raise KeyError(f"application not found: {app_id}")
    if target_status not in allowed_next(application):
        raise ValueError(
            f"非法状态跳转: {application.current_status} -> {target_status}"
        )
    history = list(application.status_history_json)
    history.append({"status": target_status, "at": _now().isoformat(), "note": note})
    application.status_history_json = history
    application.current_status = target_status
    application.updated_at = _now()
    db.commit()
    db.refresh(application)
    return application


def register_custom_status(
    db: Session, app_id: str, status: str, from_status: str, next_statuses: list[str]
) -> Application:
    application = db.get(Application, app_id)
    if application is None:
        raise KeyError(f"application not found: {app_id}")
    if status in CORE_STATUSES:
        raise ValueError(f"不能覆盖核心状态: {status}")
    custom = dict(application.custom_statuses_json)
    from_list = list(custom.get(from_status, []))
    if status not in from_list:
        from_list.append(status)
    custom[from_status] = from_list
    custom[status] = list(next_statuses)
    application.custom_statuses_json = custom
    db.commit()
    db.refresh(application)
    return application


def waiting_days(application: Application) -> int:
    history = application.status_history_json
    if not history:
        return 0
    last_at = datetime.fromisoformat(history[-1]["at"])
    return max((_now() - last_at).days, 0)


def follow_up_suggestion(application: Application) -> str:
    status = application.current_status
    days = waiting_days(application)
    if status == "applied" and days >= REMINDER_THRESHOLD_DAYS["applied"]:
        return f"已投递 {days} 天，建议礼貌询问招聘进度"
    if status == "screening" and days >= REMINDER_THRESHOLD_DAYS["screening"]:
        return f"筛选中已 {days} 天，可主动补充材料或询问流程"
    if status == "interview" and days >= REMINDER_THRESHOLD_DAYS["interview"]:
        return f"面试后 {days} 天未反馈，建议发送感谢信并询问结果"
    if status == "offer" and days >= REMINDER_THRESHOLD_DAYS["offer"]:
        return f"收到 Offer 已 {days} 天，建议确认接受时间与入职材料"
    return ""


def _resolve_jd_name(db: Session, match_id: str) -> str:
    match = db.get(Match, match_id)
    if match is None:
        return ""
    jd = db.get(JD, match.jd_id)
    return jd_display_name(jd) if jd is not None else ""


def to_payload(application: Application, jd_name: str = "") -> dict:
    payload = {
        "application_id": application.id,
        "match_id": application.match_id,
        "jd_name": jd_name,
        "current_status": application.current_status,
        "status_history": application.status_history_json,
        "allowed_next": allowed_next(application),
        "waiting_days": waiting_days(application),
        "suggestion": follow_up_suggestion(application),
        "custom_statuses": application.custom_statuses_json,
        "notes": application.notes,
        "next_action": application.next_action,
        "reminder_at": application.reminder_at.isoformat() if application.reminder_at else None,
        "created_at": application.created_at.isoformat(),
    }
    return payload


def list_applications(db: Session) -> list[dict]:
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    return [to_payload(a, _resolve_jd_name(db, a.match_id)) for a in apps]


def get_reminders(db: Session) -> list[dict]:
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    reminders = []
    for a in apps:
        if a.reminder_at and a.reminder_at <= _now():
            reminders.append(to_payload(a, _resolve_jd_name(db, a.match_id)))
        elif follow_up_suggestion(a):
            reminders.append(to_payload(a, _resolve_jd_name(db, a.match_id)))
    return reminders
