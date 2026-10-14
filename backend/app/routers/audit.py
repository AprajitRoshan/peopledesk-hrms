from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import require_admin_or_hr
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


@router.get("")
def list_audit_logs(db: Annotated[Session, Depends(get_db)],
                    admin: Annotated[User, Depends(require_admin_or_hr)],
                    limit: int = Query(100, ge=1, le=500),
                    action: str | None = Query(None, max_length=80)):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    # Intentionally read-only: no create/update/delete endpoints exist for audit logs.
    return [{"id": r.id, "actor_user_id": r.actor_user_id, "action": r.action,
             "entity_type": r.entity_type, "entity_id": r.entity_id,
             "details": r.details, "created_at": r.created_at} for r in rows]
