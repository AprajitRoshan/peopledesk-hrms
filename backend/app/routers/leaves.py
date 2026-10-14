from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.schemas.hrms import LeaveCreate, LeaveDecision, LeaveResponse
from app.services.notifications import send_template_notification

router = APIRouter(prefix="/api/leaves", tags=["Leave Management"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
HrUser = Annotated[User, Depends(require_admin_or_hr)]
DEFAULT_BALANCES = {"annual": 12, "sick": 10, "personal": 3}


class LeaveBalanceUpdate(BaseModel):
    allocated_days: int = Field(ge=0, le=365)


def working_days(start: date, end: date) -> int:
    return sum(1 for offset in range((end - start).days + 1)
               if (start + timedelta(days=offset)).weekday() < 5)


def _ensure_balances(db: Session, employee_id: int) -> list[LeaveBalance]:
    existing = {row.leave_type: row for row in db.query(LeaveBalance).filter(LeaveBalance.employee_id == employee_id).all()}
    for leave_type, days in DEFAULT_BALANCES.items():
        if leave_type not in existing:
            approved = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee_id,
                LeaveRequest.leave_type == leave_type, LeaveRequest.status == "approved").all()
            used = sum(working_days(row.start_date, row.end_date) for row in approved)
            row = LeaveBalance(employee_id=employee_id, leave_type=leave_type, allocated_days=days, used_days=used)
            db.add(row); existing[leave_type] = row
    db.flush()
    return list(existing.values())


def _serialize(db: Session, leave: LeaveRequest) -> dict:
    row = db.query(Employee.employee_code, User.full_name).join(User, User.id == Employee.user_id).filter(Employee.id == leave.employee_id).first()
    return {"id": leave.id, "employee_id": leave.employee_id, "start_date": leave.start_date,
            "end_date": leave.end_date, "leave_type": leave.leave_type, "reason": leave.reason,
            "review_note": leave.review_note, "status": leave.status, "reviewed_by": leave.reviewed_by,
            "reviewed_at": leave.reviewed_at, "created_at": leave.created_at,
            "employee_code": row[0] if row else None, "employee_name": row[1] if row else None,
            "days_requested": working_days(leave.start_date, leave.end_date)}


def _own_employee(db: Session, user: User) -> Employee:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee record not found.")
    return employee


@router.post("", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
def apply_leave(payload: LeaveCreate, db: Db, user: CurrentUser):
    employee = _own_employee(db, user)
    requested_days = working_days(payload.start_date, payload.end_date)
    if requested_days < 1:
        raise HTTPException(status_code=422, detail="Leave must include at least one weekday.")
    overlapping = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id,
        LeaveRequest.status.in_(["pending", "approved"]), LeaveRequest.start_date <= payload.end_date,
        LeaveRequest.end_date >= payload.start_date).first()
    if overlapping:
        raise HTTPException(status_code=409, detail="This date range overlaps an existing pending or approved leave request.")
    _ensure_balances(db, employee.id)
    leave = LeaveRequest(employee_id=employee.id, start_date=payload.start_date,
        end_date=payload.end_date, leave_type=payload.leave_type,
        reason=payload.reason.strip(), status="pending")
    db.add(leave); db.flush()
    write_audit_log(db, actor_user_id=user.id, action="leave.applied", entity_type="leave_request", entity_id=leave.id,
                    details={"start_date": payload.start_date.isoformat(), "end_date": payload.end_date.isoformat(), "days": requested_days})
    send_template_notification(db, recipient=user.email, template_key="leave_applied",
        context={"name": user.full_name, "start_date": payload.start_date.isoformat(), "end_date": payload.end_date.isoformat()},
        related_entity_type="leave_request", related_entity_id=leave.id)
    db.commit(); db.refresh(leave)
    return _serialize(db, leave)


@router.get("/me", response_model=list[LeaveResponse])
def my_leaves(db: Db, user: CurrentUser):
    employee = _own_employee(db, user)
    rows = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id).order_by(LeaveRequest.created_at.desc()).all()
    return [_serialize(db, row) for row in rows]


@router.get("/balance/me")
def my_leave_balances(db: Db, user: CurrentUser):
    employee = _own_employee(db, user)
    rows = _ensure_balances(db, employee.id)
    db.commit()
    return [{"employee_id": employee.id, "leave_type": row.leave_type, "allocated_days": row.allocated_days,
             "used_days": row.used_days, "available_days": row.allocated_days - row.used_days} for row in rows]


@router.get("/balance/{employee_id}")
def employee_leave_balances(employee_id: int, db: Db, actor: HrUser):
    if db.query(Employee.id).filter(Employee.id == employee_id).first() is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    rows = _ensure_balances(db, employee_id); db.commit()
    return [{"employee_id": employee_id, "leave_type": row.leave_type, "allocated_days": row.allocated_days,
             "used_days": row.used_days, "available_days": row.allocated_days - row.used_days} for row in rows]


@router.patch("/balance/{employee_id}/{leave_type}")
def update_leave_allocation(employee_id: int, leave_type: Literal["annual", "sick", "personal"],
                            payload: LeaveBalanceUpdate, db: Db, actor: HrUser):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None: raise HTTPException(status_code=404, detail="Employee not found.")
    _ensure_balances(db, employee_id)
    balance = db.query(LeaveBalance).filter_by(employee_id=employee_id, leave_type=leave_type).first()
    if payload.allocated_days < balance.used_days:
        raise HTTPException(status_code=422, detail="Allocated days cannot be lower than days already used.")
    previous = balance.allocated_days; balance.allocated_days = payload.allocated_days
    write_audit_log(db, actor_user_id=actor.id, action="leave.balance_adjusted", entity_type="leave_balance", entity_id=balance.id,
                    details={"employee_id": employee_id, "leave_type": leave_type, "previous_allocation": previous,
                             "new_allocation": payload.allocated_days})
    db.commit()
    return {"employee_id": employee_id, "leave_type": leave_type, "allocated_days": balance.allocated_days,
            "used_days": balance.used_days, "available_days": balance.allocated_days - balance.used_days}


@router.get("", response_model=list[LeaveResponse])
def list_leaves(db: Db, actor: HrUser, leave_status: str | None = Query(None, alias="status", pattern="^(pending|approved|rejected)$"),
                department: str | None = Query(None, max_length=100), limit: int = Query(100, ge=1, le=500)):
    query = db.query(LeaveRequest)
    if leave_status: query = query.filter(LeaveRequest.status == leave_status)
    if department: query = query.join(Employee, Employee.id == LeaveRequest.employee_id).filter(Employee.department == department)
    rows = query.order_by(LeaveRequest.created_at.desc()).limit(limit).all()
    return [_serialize(db, row) for row in rows]


@router.patch("/{leave_id}/decision", response_model=LeaveResponse)
def decide_leave(leave_id: int, payload: LeaveDecision, db: Db, actor: HrUser):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if leave is None: raise HTTPException(status_code=404, detail="Leave request not found.")
    if leave.status != "pending": raise HTTPException(status_code=409, detail="This leave request has already been reviewed.")
    days = working_days(leave.start_date, leave.end_date)
    if payload.decision == "approved" and leave.leave_type != "unpaid":
        balances = _ensure_balances(db, leave.employee_id)
        balance = next((row for row in balances if row.leave_type == leave.leave_type), None)
        if balance is None: raise HTTPException(status_code=422, detail="No balance is configured for this leave type.")
        if balance.allocated_days - balance.used_days < days:
            raise HTTPException(status_code=422, detail=f"Insufficient {leave.leave_type} leave balance. Available: {balance.allocated_days - balance.used_days} day(s); requested: {days}.")
        balance.used_days += days
    leave.status = payload.decision; leave.reviewed_by = actor.id; leave.reviewed_at = datetime.utcnow()
    leave.review_note = payload.review_note.strip() if payload.review_note else None
    write_audit_log(db, actor_user_id=actor.id, action=f"leave.{payload.decision}", entity_type="leave_request",
                    entity_id=leave.id, details={"review_note": leave.review_note, "days": days, "leave_type": leave.leave_type})
    employee = db.query(Employee).filter(Employee.id == leave.employee_id).first()
    user = db.query(User).filter(User.id == employee.user_id).first() if employee else None
    if user:
        send_template_notification(db, recipient=user.email, template_key="leave_decision",
            context={"name": user.full_name, "start_date": leave.start_date.isoformat(),
                     "end_date": leave.end_date.isoformat(), "decision": payload.decision},
            related_entity_type="leave_request", related_entity_id=leave.id)
    db.commit(); db.refresh(leave)
    return _serialize(db, leave)
