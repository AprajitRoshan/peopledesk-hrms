
from datetime import date, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.user import User
from app.models.work_shift import ShiftAssignment, WorkShift
from app.services.workforce import (
    calculate_attendance_shift_metrics,
    current_shift_assignment,
)


router = APIRouter(
    prefix="/api/shifts",
    tags=["Shift & Work Schedule Management"],
)

Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]
Hr = Annotated[User, Depends(require_admin_or_hr)]


class ShiftCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    shift_type: Literal["general", "night", "flexible", "remote"] = "general"
    start_time: time
    end_time: time
    grace_minutes: int = Field(ge=0, le=240, default=10)
    break_minutes: int = Field(ge=0, le=240, default=0)
    overtime_after_minutes: int = Field(ge=0, le=240, default=0)
    description: str | None = Field(None, max_length=1000)
    is_active: bool = True


class ShiftUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    shift_type: Literal["general", "night", "flexible", "remote"] | None = None
    start_time: time | None = None
    end_time: time | None = None
    grace_minutes: int | None = Field(None, ge=0, le=240)
    break_minutes: int | None = Field(None, ge=0, le=240)
    overtime_after_minutes: int | None = Field(None, ge=0, le=240)
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = None


class AssignmentCreate(BaseModel):
    shift_id: int = Field(gt=0)
    employee_id: int | None = Field(None, gt=0)
    department: str | None = Field(None, min_length=2, max_length=100)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if bool(self.employee_id) == bool(self.department):
            raise ValueError(
                "Specify exactly one target: employee_id or department."
            )
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError(
                "effective_to must be on or after effective_from."
            )
        return self


def _shift_data(row: WorkShift):
    return {
        "id": row.id,
        "name": row.name,
        "shift_type": row.shift_type,
        "start_time": row.start_time.strftime("%H:%M"),
        "end_time": row.end_time.strftime("%H:%M"),
        "grace_minutes": row.grace_minutes,
        "break_minutes": row.break_minutes,
        "overtime_after_minutes": row.overtime_after_minutes,
        "description": row.description,
        "is_active": row.is_active,
    }


def _assignment_data(db: Session, row: ShiftAssignment):
    shift = db.query(WorkShift).filter_by(id=row.shift_id).first()
    employee = (
        db.query(Employee).filter_by(id=row.employee_id).first()
        if row.employee_id else None
    )
    user = (
        db.query(User).filter_by(id=employee.user_id).first()
        if employee else None
    )

    return {
        "id": row.id,
        "shift_id": row.shift_id,
        "shift_name": shift.name if shift else "—",
        "shift_type": shift.shift_type if shift else "—",
        "employee_id": row.employee_id,
        "employee_name": user.full_name if user else None,
        "employee_code": employee.employee_code if employee else None,
        "department": row.department,
        "effective_from": row.effective_from,
        "effective_to": row.effective_to,
        "is_active": row.is_active,
        "assigned_by": row.assigned_by,
        "created_at": row.created_at,
    }


@router.get("")
def list_shifts(db: Db, user: Current, active_only: bool = True):
    query = db.query(WorkShift)
    if active_only:
        query = query.filter(WorkShift.is_active.is_(True))
    return [_shift_data(row) for row in query.order_by(WorkShift.name).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_shift(payload: ShiftCreate, db: Db, actor: Hr):
    row = WorkShift(**payload.model_dump(), created_by=actor.id)
    db.add(row)

    try:
        db.flush()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Shift name already exists or shift could not be created.",
        ) from exc

    write_audit_log(
        db,
        actor_user_id=actor.id,
        action="shift.created",
        entity_type="work_shift",
        entity_id=row.id,
        details={"name": row.name, "type": row.shift_type},
    )
    db.commit()
    db.refresh(row)
    return _shift_data(row)


@router.patch("/{shift_id}")
def update_shift(
    shift_id: int,
    payload: ShiftUpdate,
    db: Db,
    actor: Hr,
):
    row = db.query(WorkShift).filter_by(id=shift_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Shift not found.")

    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(
                status_code=422,
                detail="Shift name cannot be blank.",
            )

    for key, value in changes.items():
        setattr(row, key, value)

    write_audit_log(
        db,
        actor_user_id=actor.id,
        action="shift.updated",
        entity_type="work_shift",
        entity_id=row.id,
        details={"fields": list(changes)},
    )
    db.commit()
    db.refresh(row)
    return _shift_data(row)


@router.get("/assignments")
def list_assignments(
    db: Db,
    actor: Hr,
    active_only: bool = True,
):
    query = db.query(ShiftAssignment)
    if active_only:
        query = query.filter(ShiftAssignment.is_active.is_(True))

    rows = (
        query.order_by(
            ShiftAssignment.effective_from.desc(),
            ShiftAssignment.id.desc(),
        )
        .limit(500)
        .all()
    )
    return [_assignment_data(db, row) for row in rows]


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: AssignmentCreate,
    db: Db,
    actor: Hr,
):
    shift = (
        db.query(WorkShift)
        .filter_by(id=payload.shift_id, is_active=True)
        .first()
    )
    if not shift:
        raise HTTPException(status_code=404, detail="Active shift not found.")

    if payload.employee_id and not db.query(Employee.id).filter_by(
        id=payload.employee_id,
        employment_status="active",
    ).first():
        raise HTTPException(status_code=404, detail="Active employee not found.")

    if payload.department and not db.query(Employee.id).filter_by(
        department=payload.department,
        employment_status="active",
    ).first():
        raise HTTPException(
            status_code=404,
            detail="No active employees in that department.",
        )

    target_filter = (
        ShiftAssignment.employee_id == payload.employee_id
        if payload.employee_id
        else (
            ShiftAssignment.employee_id.is_(None)
            & (ShiftAssignment.department == payload.department)
        )
    )

    old_rows = db.query(ShiftAssignment).filter(
        target_filter,
        ShiftAssignment.is_active.is_(True),
        or_(
            ShiftAssignment.effective_to.is_(None),
            ShiftAssignment.effective_to >= payload.effective_from,
        ),
    ).all()

    for old in old_rows:
        old.is_active = False
        old.effective_to = max(
            old.effective_from,
            payload.effective_from - timedelta(days=1),
        )

    row = ShiftAssignment(
        **payload.model_dump(),
        assigned_by=actor.id,
        is_active=True,
    )
    db.add(row)
    db.flush()

    write_audit_log(
        db,
        actor_user_id=actor.id,
        action="shift.assigned",
        entity_type="shift_assignment",
        entity_id=row.id,
        details={
            "shift_id": row.shift_id,
            "employee_id": row.employee_id,
            "department": row.department,
            "effective_from": row.effective_from.isoformat(),
        },
    )
    db.commit()
    db.refresh(row)
    return _assignment_data(db, row)


@router.get("/me/current")
def my_current_shift(db: Db, user: Current):
    employee = db.query(Employee).filter_by(user_id=user.id).first()
    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee profile not found.",
        )

    assignment, shift = current_shift_assignment(db, employee, date.today())
    return {
        "employee_id": employee.id,
        "shift": _shift_data(shift) if shift else None,
        "assignment": (
            _assignment_data(db, assignment) if assignment else None
        ),
    }


@router.get("/attendance-report")
def shift_attendance_report(
    db: Db,
    actor: Hr,
    start_date: date,
    end_date: date,
    department: str | None = Query(None, max_length=100),
    shift_id: int | None = Query(None, ge=1),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="end_date must be on or after start_date.",
        )

    query = (
        db.query(Attendance, Employee, User)
        .join(Employee, Employee.id == Attendance.employee_id)
        .join(User, User.id == Employee.user_id)
        .filter(
            Attendance.work_date >= start_date,
            Attendance.work_date <= end_date,
        )
    )

    if department:
        query = query.filter(Employee.department == department)

    rows = query.order_by(
        Attendance.work_date.desc(),
        Employee.employee_code,
    ).limit(2000).all()

    records = []

    for attendance, employee, user in rows:
        assignment, assigned_shift = current_shift_assignment(
            db, employee, attendance.work_date
        )

        # An explicitly stored shift takes precedence; otherwise resolve
        # the employee/department assignment effective on that work date.
        resolved_shift_id = (
            attendance.shift_id
            if attendance.shift_id is not None
            else (assigned_shift.id if assigned_shift else None)
        )

        if shift_id is not None and resolved_shift_id != shift_id:
            continue

        # Calculate report metrics in memory only. Do not persist changes
        # to historical attendance while a report is being viewed.
        metrics = {
            "late_minutes": attendance.late_minutes,
            "early_leave_minutes": attendance.early_leave_minutes,
            "overtime_minutes": attendance.overtime_minutes,
        }

        if assigned_shift and resolved_shift_id == assigned_shift.id:
            report_copy = Attendance(
                employee_id=attendance.employee_id,
                work_date=attendance.work_date,
                check_in=attendance.check_in,
                check_out=attendance.check_out,
                status=attendance.status,
                shift_id=resolved_shift_id,
            )
            calculate_attendance_shift_metrics(db, report_copy, employee)
            metrics = {
                "late_minutes": report_copy.late_minutes,
                "early_leave_minutes": report_copy.early_leave_minutes,
                "overtime_minutes": report_copy.overtime_minutes,
            }

        worked_hours = 0.0
        if attendance.check_in and attendance.check_out:
            worked_hours = round(
                max(
                    0,
                    (
                        attendance.check_out - attendance.check_in
                    ).total_seconds() / 3600,
                ),
                2,
            )

        records.append({
            "attendance_id": attendance.id,
            "employee_id": employee.id,
            "employee_code": employee.employee_code,
            "employee_name": user.full_name,
            "department": employee.department,
            "work_date": attendance.work_date,
            "shift_id": resolved_shift_id,
            "check_in": attendance.check_in,
            "check_out": attendance.check_out,
            "status": attendance.status,
            "late_minutes": metrics["late_minutes"],
            "early_leave_minutes": metrics["early_leave_minutes"],
            "overtime_minutes": metrics["overtime_minutes"],
            "worked_hours": worked_hours,
        })

    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(records),
        "records": records,
    }
