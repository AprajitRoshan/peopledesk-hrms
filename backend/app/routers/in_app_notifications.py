from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, Field, model_validator
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.employee import Employee
from app.models.notification_center import InAppNotification, NotificationPreference
from app.models.user import User
from app.services.in_app_notifications import preferences_for, notification_payload, create_in_app_notification

router = APIRouter(prefix="/api/in-app-notifications", tags=["In-app Notification Center"])
Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]
Hr = Annotated[User, Depends(require_admin_or_hr)]

class PreferenceUpdate(BaseModel):
    leave_enabled: bool | None = None
    payroll_enabled: bool | None = None
    attendance_enabled: bool | None = None
    announcements_enabled: bool | None = None

class BroadcastCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    message: str = Field(min_length=3, max_length=4000)
    department: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def clean_message(self):
        self.title = self.title.strip()
        self.message = self.message.strip()
        if len(self.title) < 2 or len(self.message) < 3:
            raise ValueError("Title and message cannot be blank.")
        if self.department is not None:
            self.department = self.department.strip() or None
        return self

@router.get("/me")
def list_my_notifications(db: Db, user: Current, unread_only: bool = False, limit: int = Query(100, ge=1, le=300)):
    q = db.query(InAppNotification).filter(InAppNotification.user_id == user.id)
    if unread_only: q = q.filter(InAppNotification.is_read.is_(False))
    rows = q.order_by(InAppNotification.created_at.desc(), InAppNotification.id.desc()).limit(limit).all()
    unread_count = db.query(InAppNotification.id).filter(InAppNotification.user_id == user.id, InAppNotification.is_read.is_(False)).count()
    return {"unread_count": unread_count, "notifications": [notification_payload(row) for row in rows]}

@router.patch("/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Db, user: Current):
    row = db.query(InAppNotification).filter_by(id=notification_id, user_id=user.id).first()
    if not row: raise HTTPException(status_code=404, detail="Notification not found.")
    if not row.is_read:
        row.is_read = True; row.read_at = datetime.utcnow(); db.commit(); db.refresh(row)
    return notification_payload(row)

@router.post("/read-all")
def mark_all_read(db: Db, user: Current):
    now = datetime.utcnow()
    db.query(InAppNotification).filter(InAppNotification.user_id == user.id, InAppNotification.is_read.is_(False)).update(
        {"is_read": True, "read_at": now}, synchronize_session=False)
    db.commit()
    return {"message": "All notifications marked as read."}

@router.get("/preferences/me")
def get_preferences(db: Db, user: Current):
    row = preferences_for(db, user.id); db.commit(); db.refresh(row)
    return {"leave_enabled": row.leave_enabled, "payroll_enabled": row.payroll_enabled,
        "attendance_enabled": row.attendance_enabled, "announcements_enabled": row.announcements_enabled}

@router.patch("/preferences/me")
def update_preferences(payload: PreferenceUpdate, db: Db, user: Current):
    row = preferences_for(db, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
    db.commit(); db.refresh(row)
    return {"leave_enabled": row.leave_enabled, "payroll_enabled": row.payroll_enabled,
        "attendance_enabled": row.attendance_enabled, "announcements_enabled": row.announcements_enabled}

@router.post("/broadcast")
def broadcast_notification(payload: BroadcastCreate, db: Db, actor: Hr):
    query = db.query(User).filter(User.is_active.is_(True))
    if payload.department:
        query = query.join(Employee, Employee.user_id == User.id).filter(Employee.department == payload.department)
    recipients = query.all()
    created = 0
    for recipient in recipients:
        if create_in_app_notification(db, user_id=recipient.id, category="announcements", title=payload.title,
            message=payload.message, source_type="announcement", created_by=actor.id):
            created += 1
    write_audit_log(db, actor_user_id=actor.id, action="notification.broadcast", entity_type="notification", details={
        "title": payload.title, "department": payload.department, "eligible_recipients": len(recipients), "notifications_created": created})
    db.commit()
    return {"message": "Broadcast processed.", "recipients": len(recipients), "notifications_created": created}
