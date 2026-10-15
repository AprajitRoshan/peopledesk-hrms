from datetime import datetime
from sqlalchemy.orm import Session
from app.models.notification_center import InAppNotification, NotificationPreference
from app.models.user import User

CATEGORY_FIELDS = {
    "leave": "leave_enabled",
    "payroll": "payroll_enabled",
    "attendance": "attendance_enabled",
    "announcements": "announcements_enabled",
}

def preferences_for(db: Session, user_id: int) -> NotificationPreference:
    row = db.query(NotificationPreference).filter_by(user_id=user_id).first()
    if row is None:
        row = NotificationPreference(user_id=user_id)
        db.add(row); db.flush()
    return row

def create_in_app_notification(db: Session, *, user_id: int, category: str, title: str, message: str,
                               source_type: str | None = None, source_id: int | str | None = None,
                               created_by: int | None = None, respect_preferences: bool = True) -> InAppNotification | None:
    category = category if category in CATEGORY_FIELDS else "announcements"
    if respect_preferences:
        prefs = preferences_for(db, user_id)
        if not getattr(prefs, CATEGORY_FIELDS[category]):
            return None
    row = InAppNotification(user_id=user_id, category=category, title=title.strip()[:180],
        message=message.strip(), source_type=source_type,
        source_id=str(source_id) if source_id is not None else None, created_by=created_by, is_read=False)
    db.add(row)
    return row

def notify_hr_admins(db: Session, *, category: str, title: str, message: str,
                     source_type: str | None = None, source_id: int | str | None = None,
                     created_by: int | None = None) -> int:
    users = db.query(User).filter(User.is_active.is_(True), User.role.in_(["admin", "hr"])).all()
    count = 0
    for user in users:
        if create_in_app_notification(db, user_id=user.id, category=category, title=title, message=message,
                                      source_type=source_type, source_id=source_id, created_by=created_by):
            count += 1
    return count

def notification_payload(row: InAppNotification) -> dict:
    return {"id": row.id, "user_id": row.user_id, "category": row.category, "title": row.title,
        "message": row.message, "source_type": row.source_type, "source_id": row.source_id,
        "is_read": row.is_read, "created_at": row.created_at, "read_at": row.read_at}
