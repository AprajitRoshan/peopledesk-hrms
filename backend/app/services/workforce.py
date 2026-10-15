from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.employee import Employee
from app.models.holiday import Holiday, OptionalHolidaySelection
from app.models.work_shift import ShiftAssignment, WorkShift
from app.models.attendance import Attendance

WORK_TZ = ZoneInfo("Asia/Kolkata")

def holiday_dates(db: Session, start: date, end: date, employee: Employee | None = None, *, include_optional: bool = False) -> set[date]:
    if end < start:
        return set()
    query = db.query(Holiday).filter(Holiday.is_active.is_(True), Holiday.holiday_date >= start, Holiday.holiday_date <= end)
    if employee:
        query = query.filter(or_(Holiday.department.is_(None), Holiday.department == employee.department))
        # A regional holiday only applies when the employee's profile region matches.
        query = query.filter(or_(Holiday.region.is_(None), Holiday.region == employee.region))
    rows = query.all()
    selected = set()
    if employee and not include_optional:
        optional_ids = {r[0] for r in db.query(OptionalHolidaySelection.holiday_id).filter_by(employee_id=employee.id).all()}
        selected = optional_ids
    result = set()
    for row in rows:
        if row.holiday_type == "optional" and employee and row.id not in selected and not include_optional:
            continue
        if row.holiday_type == "optional" and employee is None and not include_optional:
            continue
        result.add(row.holiday_date)
    return result

def is_working_weekday(db: Session, day: date, employee: Employee | None = None) -> bool:
    return day.weekday() < 5 and day not in holiday_dates(db, day, day, employee)

def working_days_excluding_holidays(db: Session, start: date, end: date, employee: Employee | None = None) -> int:
    if end < start: return 0
    holidays = holiday_dates(db, start, end, employee)
    return sum(1 for offset in range((end - start).days + 1)
               if (d := start + timedelta(days=offset)).weekday() < 5 and d not in holidays)

def current_shift_assignment(db: Session, employee: Employee, on_date: date) -> tuple[ShiftAssignment | None, WorkShift | None]:
    q = db.query(ShiftAssignment, WorkShift).join(WorkShift, WorkShift.id == ShiftAssignment.shift_id).filter(
        ShiftAssignment.is_active.is_(True), WorkShift.is_active.is_(True), ShiftAssignment.effective_from <= on_date,
        or_(ShiftAssignment.effective_to.is_(None), ShiftAssignment.effective_to >= on_date),
        or_(ShiftAssignment.employee_id == employee.id,
            (ShiftAssignment.employee_id.is_(None) & (ShiftAssignment.department == employee.department))))
    rows = q.order_by((ShiftAssignment.employee_id == employee.id).desc(), ShiftAssignment.effective_from.desc(), ShiftAssignment.id.desc()).all()
    return rows[0] if rows else (None, None)

def local_datetime(value: datetime | None) -> datetime | None:
    if value is None: return None
    return value.replace(tzinfo=timezone.utc).astimezone(WORK_TZ).replace(tzinfo=None)

def shift_bounds(day: date, shift: WorkShift) -> tuple[datetime, datetime]:
    start = datetime.combine(day, shift.start_time)
    end_day = day + timedelta(days=1) if shift.end_time <= shift.start_time else day
    return start, datetime.combine(end_day, shift.end_time)

def calculate_attendance_shift_metrics(db: Session, record: Attendance, employee: Employee) -> dict:
    assignment, shift = current_shift_assignment(db, employee, record.work_date)
    record.shift_id = shift.id if shift else None
    record.late_minutes = 0
    record.early_leave_minutes = 0
    record.overtime_minutes = 0
    if shift is None:
        return {"shift": None, "late_minutes": 0, "early_leave_minutes": 0, "overtime_minutes": 0}
    planned_start, planned_end = shift_bounds(record.work_date, shift)
    check_in = local_datetime(record.check_in)
    check_out = local_datetime(record.check_out)
    if check_in:
        allowed_start = planned_start + timedelta(minutes=shift.grace_minutes)
        record.late_minutes = max(0, int((check_in - allowed_start).total_seconds() // 60))
    if check_out:
        if shift.end_time <= shift.start_time and check_out < planned_start:
            check_out += timedelta(days=1)
        record.early_leave_minutes = max(0, int((planned_end - check_out).total_seconds() // 60)) if check_out < planned_end else 0
        if check_out > planned_end + timedelta(minutes=shift.overtime_after_minutes):
            record.overtime_minutes = max(0, int((check_out - (planned_end + timedelta(minutes=shift.overtime_after_minutes))).total_seconds() // 60))
    return {"shift": shift, "late_minutes": record.late_minutes, "early_leave_minutes": record.early_leave_minutes,
            "overtime_minutes": record.overtime_minutes}
