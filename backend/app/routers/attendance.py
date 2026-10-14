from datetime import date, datetime, timezone
from calendar import monthrange
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.user import User
from app.schemas.hrms import AttendanceResponse

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
HrUser = Annotated[User, Depends(require_admin_or_hr)]


class AttendanceOverride(BaseModel):
    employee_id: int = Field(gt=0)
    work_date: date
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: Literal["present", "absent", "leave", "half_day"] = "present"
    correction_note: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_times(self):
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValueError("Check-out cannot be earlier than check-in.")
        return self


def my_employee(db: Session, user: User) -> Employee:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee record not found.")
    return employee


def now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def month_dates(month: str) -> tuple[date, date]:
    try:
        year, month_number = map(int, month.split("-"))
        first = date(year, month_number, 1)
        last = date(year, month_number, monthrange(year, month_number)[1])
        return first, last
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="month must be formatted as YYYY-MM.")


@router.post("/check-in", response_model=AttendanceResponse)
def check_in(db: Db, user: CurrentUser):
    employee = my_employee(db, user)
    today = date.today()
    record = db.query(Attendance).filter(Attendance.employee_id == employee.id, Attendance.work_date == today).first()
    if record and record.check_in:
        raise HTTPException(status_code=409, detail="You have already checked in today.")
    now = now_utc_naive()
    if record is None:
        record = Attendance(employee_id=employee.id, work_date=today, check_in=now, status="present")
        db.add(record)
    else:
        record.check_in = now; record.status = "present"
    db.flush()
    write_audit_log(db, actor_user_id=user.id, action="attendance.checked_in", entity_type="attendance", entity_id=record.id,
                    details={"employee_id": employee.id, "work_date": today.isoformat()})
    db.commit(); db.refresh(record)
    return record


@router.post("/check-out", response_model=AttendanceResponse)
def check_out(db: Db, user: CurrentUser):
    employee = my_employee(db, user)
    record = db.query(Attendance).filter(Attendance.employee_id == employee.id, Attendance.work_date == date.today()).first()
    if record is None or record.check_in is None:
        raise HTTPException(status_code=409, detail="Check in before checking out.")
    if record.check_out is not None:
        raise HTTPException(status_code=409, detail="You have already checked out today.")
    now = now_utc_naive()
    if now < record.check_in:
        raise HTTPException(status_code=409, detail="Current time is earlier than the recorded check-in.")
    record.check_out = now
    write_audit_log(db, actor_user_id=user.id, action="attendance.checked_out", entity_type="attendance", entity_id=record.id,
                    details={"employee_id": employee.id, "work_date": record.work_date.isoformat()})
    db.commit(); db.refresh(record)
    return record


@router.get("/me", response_model=list[AttendanceResponse])
def my_attendance(db: Db, user: CurrentUser, start_date: date | None = None, end_date: date | None = None,
                  limit: int = Query(31, ge=1, le=100)):
    employee = my_employee(db, user)
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
    query = db.query(Attendance).filter(Attendance.employee_id == employee.id)
    if start_date: query = query.filter(Attendance.work_date >= start_date)
    if end_date: query = query.filter(Attendance.work_date <= end_date)
    return query.order_by(Attendance.work_date.desc()).limit(limit).all()


@router.get("/summary/me")
def my_monthly_summary(db: Db, user: CurrentUser, month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    employee = my_employee(db, user)
    first, last = month_dates(month)
    rows = db.query(Attendance).filter(Attendance.employee_id == employee.id,
        Attendance.work_date >= first, Attendance.work_date <= last).all()
    worked_hours = sum((max(0, (row.check_out - row.check_in).total_seconds() / 3600)
                        if row.check_in and row.check_out else 0) for row in rows)
    return {"month": month, "employee_id": employee.id, "employee_code": employee.employee_code,
        "attendance_days": sum(1 for row in rows if row.check_in and row.status == "present"),
        "absent_days": sum(1 for row in rows if row.status == "absent"),
        "leave_days": sum(1 for row in rows if row.status == "leave"),
        "worked_hours": round(worked_hours, 2), "records": len(rows)}


@router.get("/summary")
def all_monthly_summaries(db: Db, actor: HrUser, month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                          department: str | None = Query(None, max_length=100)):
    first, last = month_dates(month)
    query = db.query(Employee, User).join(User, User.id == Employee.user_id)
    if department: query = query.filter(Employee.department == department)
    employees = query.order_by(Employee.employee_code).all()
    summaries = []
    for employee, user in employees:
        rows = db.query(Attendance).filter(Attendance.employee_id == employee.id,
            Attendance.work_date >= first, Attendance.work_date <= last).all()
        worked_hours = sum((max(0, (row.check_out - row.check_in).total_seconds() / 3600)
                            if row.check_in and row.check_out else 0) for row in rows)
        summaries.append({"employee_id": employee.id, "employee_code": employee.employee_code,
            "employee_name": user.full_name, "department": employee.department,
            "attendance_days": sum(1 for row in rows if row.check_in and row.status == "present"),
            "absent_days": sum(1 for row in rows if row.status == "absent"),
            "leave_days": sum(1 for row in rows if row.status == "leave"),
            "worked_hours": round(worked_hours, 2), "records": len(rows)})
    return {"month": month, "employee_count": len(summaries), "employees": summaries}


@router.get("", response_model=list[AttendanceResponse])
def all_attendance(db: Db, actor: HrUser, work_date: date | None = None,
                   employee_id: int | None = Query(None, ge=1), department: str | None = Query(None, max_length=100),
                   start_date: date | None = None, end_date: date | None = None,
                   limit: int = Query(100, ge=1, le=500)):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
    query = db.query(Attendance)
    if department: query = query.join(Employee, Employee.id == Attendance.employee_id).filter(Employee.department == department)
    if work_date: query = query.filter(Attendance.work_date == work_date)
    if start_date: query = query.filter(Attendance.work_date >= start_date)
    if end_date: query = query.filter(Attendance.work_date <= end_date)
    if employee_id: query = query.filter(Attendance.employee_id == employee_id)
    return query.order_by(Attendance.work_date.desc(), Attendance.id.desc()).limit(limit).all()


@router.post("/override", response_model=AttendanceResponse)
def attendance_override(payload: AttendanceOverride, db: Db, actor: HrUser):
    employee = db.query(Employee).filter(Employee.id == payload.employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    record = db.query(Attendance).filter(Attendance.employee_id == employee.id, Attendance.work_date == payload.work_date).first()
    before = None if record is None else {"check_in": str(record.check_in), "check_out": str(record.check_out), "status": record.status}
    if record is None:
        record = Attendance(employee_id=employee.id, work_date=payload.work_date)
        db.add(record)
    record.check_in, record.check_out = payload.check_in, payload.check_out
    record.status, record.correction_note = payload.status, payload.correction_note.strip()
    db.flush()
    write_audit_log(db, actor_user_id=actor.id, action="attendance.admin_override", entity_type="attendance", entity_id=record.id,
        details={"employee_id": employee.id, "work_date": payload.work_date.isoformat(), "before": before,
                 "after": {"check_in": str(record.check_in), "check_out": str(record.check_out), "status": record.status},
                 "correction_note": payload.correction_note.strip()})
    db.commit(); db.refresh(record)
    return record
