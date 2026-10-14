from typing import Annotated, Literal
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import require_admin
from app.database import get_db
from app.models.employee import Employee
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["Role and Permission Management"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(require_admin)]


class RoleUpdate(BaseModel):
    role: Literal["admin", "hr", "employee"]


class AccountStatusUpdate(BaseModel):
    is_active: bool


def _user_payload(user: User, employee: Employee | None) -> dict:
    return {"id": user.id, "full_name": user.full_name, "email": user.email, "role": user.role,
            "is_active": user.is_active, "employee_id": employee.id if employee else None,
            "employee_code": employee.employee_code if employee else None,
            "department": employee.department if employee else None}


def _prevent_last_admin(db: Session, target: User, requested_role: str | None = None, active: bool | None = None):
    would_remove = target.role == "admin" and ((requested_role is not None and requested_role != "admin") or active is False)
    if would_remove and target.is_active:
        active_admins = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The system must retain at least one active administrator.")


@router.get("/users")
def list_users(db: Db, actor: Admin, search: str | None = Query(None, max_length=100)):
    query = db.query(User, Employee).outerjoin(Employee, Employee.user_id == User.id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter((User.full_name.ilike(term)) | (User.email.ilike(term)) | (Employee.employee_code.ilike(term)))
    rows = query.order_by(User.id.asc()).limit(500).all()
    return [_user_payload(user, employee) for user, employee in rows]


@router.patch("/users/{user_id}/role")
def update_user_role(user_id: int, payload: RoleUpdate, db: Db, actor: Admin):
    target = db.query(User).filter(User.id == user_id).first()
    if not target: raise HTTPException(status_code=404, detail="User not found.")
    _prevent_last_admin(db, target, requested_role=payload.role)
    previous = target.role; target.role = payload.role
    write_audit_log(db, actor_user_id=actor.id, action="user.role_changed", entity_type="user", entity_id=target.id,
                    details={"previous_role": previous, "new_role": payload.role})
    db.commit()
    employee = db.query(Employee).filter(Employee.user_id == target.id).first()
    return _user_payload(target, employee)


@router.patch("/users/{user_id}/status")
def update_user_status(user_id: int, payload: AccountStatusUpdate, db: Db, actor: Admin):
    target = db.query(User).filter(User.id == user_id).first()
    if not target: raise HTTPException(status_code=404, detail="User not found.")
    _prevent_last_admin(db, target, active=payload.is_active)
    target.is_active = payload.is_active
    employee = db.query(Employee).filter(Employee.user_id == target.id).first()
    if employee:
        employee.employment_status = "active" if payload.is_active else "inactive"
    write_audit_log(db, actor_user_id=actor.id, action="user.activated" if payload.is_active else "user.deactivated",
                    entity_type="user", entity_id=target.id, details={"is_active": payload.is_active})
    db.commit()
    return _user_payload(target, employee)
