from calendar import monthrange
from datetime import date, datetime, timedelta
import json
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import Annotated
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.leave_request import LeaveRequest
from app.models.notification_log import NotificationLog
from app.models.payroll import PayrollRecord
from app.models.user import User
from app.models.compensation import CompensationRevision, SalaryComponent
from app.services.workforce import working_days_excluding_holidays, holiday_dates
from app.services.in_app_notifications import create_in_app_notification
from app.schemas.payroll import PayrollAdjustment, PayrollCreate, PayrollResponse
from app.services.notifications import send_template_notification

router = APIRouter(prefix="/api/payroll", tags=["Payroll Management"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
HrUser = Annotated[User, Depends(require_admin_or_hr)]
CENT = Decimal("0.01")


def _period_dates(period: str) -> tuple[date, date, int]:
    try:
        year, month = map(int, period.split("-"))
        return date(year, month, 1), date(year, month, monthrange(year, month)[1]), monthrange(year, month)[1]
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="pay_period must use YYYY-MM format.")


def _weekdays(db: Session, start: date, end: date, employee: Employee | None = None) -> int:
    return working_days_excluding_holidays(db, start, end, employee)


def _approved_leave_days(db: Session, employee: Employee, first: date, last: date, leave_types: set[str]) -> int:
    rows = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id,
        LeaveRequest.status == "approved", LeaveRequest.leave_type.in_(leave_types),
        LeaveRequest.start_date <= last, LeaveRequest.end_date >= first).all()
    used_dates: set[date] = set()
    holidays = holiday_dates(db, first, last, employee)
    for leave in rows:
        overlap_start, overlap_end = max(first, leave.start_date), min(last, leave.end_date)
        for offset in range((overlap_end - overlap_start).days + 1):
            day = overlap_start + timedelta(days=offset)
            if day.weekday() < 5 and day not in holidays:
                used_dates.add(day)
    return len(used_dates)


def _payroll_facts(db: Session, employee: Employee, period: str, base_salary: Decimal) -> dict:
    first, last, _ = _period_dates(period)
    holidays = holiday_dates(db, first, last, employee)
    attendance_rows = db.query(Attendance).filter(Attendance.employee_id == employee.id,
        Attendance.work_date >= first, Attendance.work_date <= last).all()
    counted_days = {row.work_date for row in attendance_rows if row.check_in and row.status == "present"
                    and row.work_date.weekday() < 5 and row.work_date not in holidays}
    paid_leave_days = _approved_leave_days(db, employee, first, last, {"annual", "sick", "personal"})
    unpaid_rows = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id,
        LeaveRequest.status == "approved", LeaveRequest.leave_type == "unpaid",
        LeaveRequest.start_date <= last, LeaveRequest.end_date >= first).all()
    lop_dates: set[date] = set()
    for leave in unpaid_rows:
        overlap_start, overlap_end = max(first, leave.start_date), min(last, leave.end_date)
        for offset in range((overlap_end - overlap_start).days + 1):
            day = overlap_start + timedelta(days=offset)
            if day.weekday() < 5 and day not in holidays:
                lop_dates.add(day)
    lop_dates.update(row.work_date for row in attendance_rows if row.status == "absent"
                     and row.work_date.weekday() < 5 and row.work_date not in holidays)
    workdays = _weekdays(db, first, last, employee)
    lop_days = len(lop_dates)
    lop_deduction = ((base_salary / Decimal(max(workdays, 1))) * Decimal(lop_days)).quantize(CENT, rounding=ROUND_HALF_UP)
    overtime_minutes = sum(max(0, int(row.overtime_minutes or 0)) for row in attendance_rows)
    overtime_hours = (Decimal(overtime_minutes) / Decimal(60)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    holidays_in_period = len(holidays)
    return {"attendance_days": len(counted_days), "paid_leave_days": paid_leave_days,
        "lop_days": lop_days, "lop_deduction": lop_deduction, "workdays": workdays,
        "overtime_hours": overtime_hours, "holidays": holidays_in_period}


def _effective_compensation(db: Session, employee_id: int, period_start: date):
    return (db.query(CompensationRevision)
        .filter(CompensationRevision.employee_id == employee_id,
                CompensationRevision.effective_from <= period_start,
                (CompensationRevision.effective_to.is_(None) | (CompensationRevision.effective_to >= period_start)))
        .order_by(CompensationRevision.effective_from.desc(), CompensationRevision.id.desc())
        .first())


def _configured_components(db: Session, base_salary: Decimal, basic_pay: Decimal):
    items = []
    earnings = Decimal("0.00")
    deductions = Decimal("0.00")
    rows = db.query(SalaryComponent).filter(SalaryComponent.is_active.is_(True)).order_by(SalaryComponent.id).all()

    # Resolve the optional BASIC component first so percentage-based components
    # use the final basic-pay value regardless of creation order.
    basic_component = next((row for row in rows if row.code.upper() in {"BASIC", "BASIC_PAY"}
                            and row.component_type == "earning"), None)
    revised_basic = basic_pay
    if basic_component:
        amount = Decimal(basic_component.amount or 0)
        if basic_component.calculation_type == "percent_basic":
            amount = (base_salary * amount / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
        else:
            amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
        revised_basic = amount

    for component in rows:
        amount = Decimal(component.amount or 0)
        if component is basic_component:
            items.append({"name": component.name, "code": component.code, "component_type": "basic", "amount": str(revised_basic)})
            continue
        if component.calculation_type == "percent_basic":
            amount = (revised_basic * amount / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
        else:
            amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
        items.append({"name": component.name, "code": component.code, "component_type": component.component_type, "amount": str(amount)})
        if component.component_type == "earning": earnings += amount
        else: deductions += amount
    return revised_basic, earnings.quantize(CENT, rounding=ROUND_HALF_UP), deductions.quantize(CENT, rounding=ROUND_HALF_UP), items


def _payload_joined(record: PayrollRecord, employee: Employee, user: User) -> dict:
    try:
        breakdown = json.loads(record.component_breakdown or "[]")
    except (TypeError, ValueError):
        breakdown = []
    return {"id": record.id, "employee_id": record.employee_id, "employee_code": employee.employee_code,
        "employee_name": user.full_name, "email": user.email, "department": employee.department,
        "designation": employee.designation, "pay_period": record.pay_period, "base_salary": record.base_salary,
        "basic_pay": record.basic_pay, "allowances": record.allowances, "bonus": record.bonus, "variable_pay": record.variable_pay,
        "overtime_hours": record.overtime_hours, "overtime_pay": record.overtime_pay,
        "component_earning_total": record.component_earning_total, "component_deduction_total": record.component_deduction_total,
        "component_breakdown": breakdown, "deductions": record.deductions,
        "adjustment_amount": record.adjustment_amount, "adjustment_note": record.adjustment_note,
        "attendance_days": record.attendance_days, "paid_leave_days": record.paid_leave_days,
        "lop_days": record.lop_days, "lop_deduction": record.lop_deduction,
        "net_salary": record.net_salary, "status": record.status, "locked_at": record.locked_at,
        "credited_at": record.credited_at, "processed_at": record.processed_at}


def _payload(db: Session, record: PayrollRecord) -> dict:
    row = db.query(Employee, User).join(User, User.id == Employee.user_id).filter(Employee.id == record.employee_id).first()
    if not row: raise HTTPException(status_code=404, detail="Employee record not found.")
    return _payload_joined(record, row[0], row[1])


@router.get("", response_model=list[PayrollResponse])
def list_payroll(db: Db, actor: HrUser, period: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                 department: str | None = Query(None, max_length=100), limit: int = Query(200, ge=1, le=500)):
    query = db.query(PayrollRecord, Employee, User).join(Employee, Employee.id == PayrollRecord.employee_id).join(User, User.id == Employee.user_id)
    if period: query = query.filter(PayrollRecord.pay_period == period)
    if department: query = query.filter(Employee.department == department)
    rows = query.order_by(PayrollRecord.pay_period.desc(), PayrollRecord.id.desc()).limit(limit).all()
    return [_payload_joined(record, employee, user) for record, employee, user in rows]


@router.get("/compensation-preview")
def compensation_preview(
    db: Db,
    actor: HrUser,
    employee_id: int = Query(..., ge=1),
    period: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
):
    """Preview the exact effective-dated compensation inputs used for payroll.

    This endpoint is read-only. It does not create or modify payroll records.
    """
    employee = db.query(Employee).filter(
        Employee.id == employee_id, Employee.employment_status == "active"
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Active employee not found.")

    period_start, _, _ = _period_dates(period)
    revision = _effective_compensation(db, employee.id, period_start)
    if revision:
        base_salary = Decimal(revision.base_salary or 0)
        basic_pay = Decimal(revision.basic_pay or 0)
        allowances = Decimal(revision.allowances or 0)
        bonus = Decimal(revision.bonus or 0)
        variable_pay = Decimal(revision.variable_pay or 0)
        deductions = Decimal(revision.other_deductions or 0)
        overtime_multiplier = Decimal(revision.overtime_multiplier or 1.5)
        salary_source = "compensation_revision"
        effective_from = revision.effective_from
        effective_to = revision.effective_to
        revision_id = revision.id
    else:
        base_salary = Decimal(employee.monthly_salary or 0)
        basic_pay = (base_salary * Decimal("0.50")).quantize(CENT, rounding=ROUND_HALF_UP)
        allowances = bonus = variable_pay = deductions = Decimal("0.00")
        overtime_multiplier = Decimal("1.5")
        salary_source = "employee_profile"
        effective_from = effective_to = revision_id = None

    basic_pay, component_earnings, component_deductions, component_items = _configured_components(
        db, base_salary, basic_pay
    )
    facts = _payroll_facts(db, employee, period, base_salary)
    hourly_rate = base_salary / Decimal(max(facts["workdays"], 1)) / Decimal(8)
    overtime_pay = (
        hourly_rate * facts["overtime_hours"] * overtime_multiplier
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    gross_before_deductions = (
        base_salary + allowances + bonus + variable_pay + component_earnings + overtime_pay
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    estimated_net = (
        gross_before_deductions - deductions - component_deductions - facts["lop_deduction"]
    ).quantize(CENT, rounding=ROUND_HALF_UP)

    warnings = []
    hra_component = next(
        (item for item in component_items if item["code"].upper() == "HRA" and item["component_type"] == "earning"),
        None,
    )
    if hra_component and allowances > 0:
        warnings.append(
            "Both revision allowances and the configured HRA component are included in payroll. "
            f"Revision allowances: INR {allowances:,.2f}; HRA component: INR {Decimal(hra_component['amount']):,.2f}. "
            "If the revision allowance is the same HRA amount, set revision allowances to 0 to avoid double-counting."
        )

    existing_record = db.query(PayrollRecord.id).filter(
        PayrollRecord.employee_id == employee.id, PayrollRecord.pay_period == period
    ).first()
    return {
        "employee_id": employee.id,
        "employee_name": db.query(User.full_name).filter(User.id == employee.user_id).scalar(),
        "employee_code": employee.employee_code,
        "pay_period": period,
        "period_start": period_start,
        "salary_source": salary_source,
        "revision_id": revision_id,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "base_salary": base_salary,
        "basic_pay": basic_pay,
        "allowances": allowances,
        "bonus": bonus,
        "variable_pay": variable_pay,
        "other_deductions": deductions,
        "overtime_multiplier": overtime_multiplier,
        "configured_components": component_items,
        "component_earning_total": component_earnings,
        "component_deduction_total": component_deductions,
        "overtime_hours": facts["overtime_hours"],
        "overtime_pay": overtime_pay,
        "lop_days": facts["lop_days"],
        "lop_deduction": facts["lop_deduction"],
        "gross_before_deductions": gross_before_deductions,
        "estimated_net_salary": estimated_net,
        "warnings": warnings,
        "payroll_already_exists": existing_record is not None,
    }


@router.post("", response_model=PayrollResponse, status_code=201)
def process_payroll(payload: PayrollCreate, db: Db, actor: HrUser):
    employee = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.employment_status == "active").first()
    if not employee: raise HTTPException(status_code=404, detail="Active employee not found.")
    if db.query(PayrollRecord.id).filter(PayrollRecord.employee_id == employee.id, PayrollRecord.pay_period == payload.pay_period).first():
        raise HTTPException(status_code=409, detail="Payroll already exists for this employee and period. Duplicate processing is blocked.")
    first, _, _ = _period_dates(payload.pay_period)
    revision = _effective_compensation(db, employee.id, first)
    base_salary = payload.base_salary if payload.base_salary is not None else Decimal(revision.base_salary if revision else employee.monthly_salary or 0)
    if base_salary <= 0:
        raise HTTPException(status_code=422, detail="Set the employee's monthly salary or provide an effective compensation revision before processing payroll.")
    basic_pay = Decimal(revision.basic_pay if revision else (base_salary * Decimal("0.50")).quantize(CENT, rounding=ROUND_HALF_UP))
    allowances = (Decimal(revision.allowances or 0) if revision else Decimal("0.00")) + Decimal(payload.allowances or 0)
    bonus = (Decimal(revision.bonus or 0) if revision else Decimal("0.00")) + Decimal(payload.bonus or 0)
    variable_pay = (Decimal(revision.variable_pay or 0) if revision else Decimal("0.00")) + Decimal(payload.variable_pay or 0)
    deductions = (Decimal(revision.other_deductions or 0) if revision else Decimal("0.00")) + Decimal(payload.deductions or 0)
    overtime_multiplier = Decimal(revision.overtime_multiplier if revision else Decimal("1.5"))
    basic_pay, component_earnings, component_deductions, component_items = _configured_components(db, base_salary, basic_pay)
    facts = _payroll_facts(db, employee, payload.pay_period, base_salary)
    # A scheduled shift defines the regular duration. Use 8 hours as the baseline for employees without a shift assignment.
    hourly_rate = base_salary / Decimal(max(facts["workdays"], 1)) / Decimal(8)
    overtime_pay = (hourly_rate * facts["overtime_hours"] * overtime_multiplier).quantize(CENT, rounding=ROUND_HALF_UP)
    net_salary = (base_salary + allowances + bonus + variable_pay + component_earnings + overtime_pay + payload.adjustment_amount
                  - deductions - component_deductions - facts["lop_deduction"]).quantize(CENT, rounding=ROUND_HALF_UP)
    if net_salary < 0: raise HTTPException(status_code=422, detail="Net salary cannot be negative after deductions.")
    breakdown = component_items + [
        {"name": "Base/basic pay", "code": "BASIC_PAY", "component_type": "basic", "amount": str(basic_pay)},
        {"name": "Allowances", "code": "ALLOWANCES", "component_type": "earning", "amount": str(allowances)},
        {"name": "Bonus", "code": "BONUS", "component_type": "earning", "amount": str(bonus)},
        {"name": "Variable pay", "code": "VARIABLE_PAY", "component_type": "earning", "amount": str(variable_pay)},
        {"name": "Overtime pay", "code": "OVERTIME", "component_type": "earning", "amount": str(overtime_pay)},
        {"name": "Other deductions", "code": "OTHER_DEDUCTIONS", "component_type": "deduction", "amount": str(deductions)},
    ]
    record = PayrollRecord(employee_id=employee.id, pay_period=payload.pay_period, base_salary=base_salary, basic_pay=basic_pay,
        allowances=allowances, bonus=bonus, variable_pay=variable_pay, overtime_hours=facts["overtime_hours"], overtime_pay=overtime_pay,
        component_earning_total=component_earnings, component_deduction_total=component_deductions, component_breakdown=json.dumps(breakdown),
        deductions=deductions, adjustment_amount=payload.adjustment_amount,
        adjustment_note=payload.adjustment_note.strip() if payload.adjustment_note else None,
        attendance_days=facts["attendance_days"], paid_leave_days=facts["paid_leave_days"],
        lop_days=facts["lop_days"], lop_deduction=facts["lop_deduction"],
        net_salary=net_salary, status="processed", processed_by=actor.id)
    try:
        db.add(record); db.flush()
        user = db.query(User).filter(User.id == employee.user_id).first()
        details = {"employee_id": employee.id, "period": payload.pay_period, "net_salary": str(net_salary),
                   "attendance_days": facts["attendance_days"], "paid_leave_days": facts["paid_leave_days"],
                   "lop_days": facts["lop_days"], "lop_deduction": str(facts["lop_deduction"]),
                   "overtime_hours": str(facts["overtime_hours"]), "overtime_pay": str(overtime_pay), "holiday_days": facts["holidays"]}
        write_audit_log(db, actor_user_id=actor.id, action="payroll.processed", entity_type="payroll_record", entity_id=record.id, details=details)
        if user:
            send_template_notification(db, recipient=user.email, template_key="payroll_processed",
                context={"name": user.full_name, "period": payload.pay_period}, related_entity_type="payroll_record", related_entity_id=record.id)
            send_template_notification(db, recipient=user.email, template_key="salary_slip_generated",
                context={"name": user.full_name, "period": payload.pay_period}, related_entity_type="payroll_record", related_entity_id=record.id)
            create_in_app_notification(db, user_id=user.id, category="payroll", title="Payroll processed",
                message=f"Your payroll for {payload.pay_period} has been processed. Net pay: INR {net_salary:,.2f}.",
                source_type="payroll_record", source_id=record.id, created_by=actor.id)
        db.commit(); db.refresh(record)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Payroll already exists for this employee and period.") from exc
    return _payload(db, record)


@router.patch("/{record_id}/adjustment", response_model=PayrollResponse)
def adjust_payroll(record_id: int, payload: PayrollAdjustment, db: Db, actor: HrUser):
    record = db.query(PayrollRecord).filter(PayrollRecord.id == record_id).first()
    if not record: raise HTTPException(status_code=404, detail="Payroll record not found.")
    if record.status in {"locked", "credited"} or record.locked_at is not None:
        raise HTTPException(status_code=409, detail="This payroll is locked. Unlocking is not enabled; create a correction in a future payroll period.")
    net_salary = (record.base_salary + record.allowances + record.bonus + record.variable_pay + record.overtime_pay + record.component_earning_total
                  + payload.adjustment_amount - record.deductions - record.component_deduction_total - record.lop_deduction).quantize(CENT, rounding=ROUND_HALF_UP)
    if net_salary < 0: raise HTTPException(status_code=422, detail="Adjustment would make net salary negative.")
    previous_amount = record.adjustment_amount
    record.adjustment_amount, record.adjustment_note, record.net_salary = payload.adjustment_amount, payload.adjustment_note.strip(), net_salary
    employee = db.query(Employee).filter(Employee.id == record.employee_id).first()
    user = db.query(User).filter(User.id == employee.user_id).first() if employee else None
    write_audit_log(db, actor_user_id=actor.id, action="payroll.adjusted", entity_type="payroll_record", entity_id=record.id,
        details={"previous_adjustment": str(previous_amount), "adjustment_amount": str(payload.adjustment_amount), "pay_period": record.pay_period})
    if user:
        send_template_notification(db, recipient=user.email, template_key="payroll_processed",
            context={"name": user.full_name, "period": record.pay_period}, related_entity_type="payroll_record", related_entity_id=record.id)
        create_in_app_notification(db, user_id=user.id, category="payroll", title="Payroll adjustment updated",
            message=f"Your payroll adjustment for {record.pay_period} has been updated.", source_type="payroll_record", source_id=record.id, created_by=actor.id)
    db.commit(); db.refresh(record)
    return _payload(db, record)


@router.post("/{record_id}/lock", response_model=PayrollResponse)
def lock_payroll(record_id: int, db: Db, actor: HrUser):
    record = db.query(PayrollRecord).filter(PayrollRecord.id == record_id).first()
    if not record: raise HTTPException(status_code=404, detail="Payroll record not found.")
    if record.status == "credited": raise HTTPException(status_code=409, detail="Already credited; the payroll is locked.")
    if record.status == "locked": raise HTTPException(status_code=409, detail="Payroll is already locked.")
    record.status, record.locked_at = "locked", datetime.utcnow()
    write_audit_log(db, actor_user_id=actor.id, action="payroll.locked", entity_type="payroll_record", entity_id=record.id,
                    details={"employee_id": record.employee_id, "pay_period": record.pay_period})
    db.commit(); db.refresh(record)
    return _payload(db, record)


@router.post("/{record_id}/credit", response_model=PayrollResponse)
def simulate_salary_credit(record_id: int, db: Db, actor: HrUser):
    record = db.query(PayrollRecord).filter(PayrollRecord.id == record_id).first()
    if not record: raise HTTPException(status_code=404, detail="Payroll record not found.")
    if record.status == "credited": raise HTTPException(status_code=409, detail="Salary credit has already been simulated.")
    if record.status != "locked": raise HTTPException(status_code=409, detail="Lock payroll before simulating salary credit.")
    record.status, record.credited_at = "credited", datetime.utcnow()
    write_audit_log(db, actor_user_id=actor.id, action="payroll.salary_credit_simulated", entity_type="payroll_record", entity_id=record.id,
                    details={"employee_id": record.employee_id, "pay_period": record.pay_period, "net_salary": str(record.net_salary), "simulation_only": True})
    employee = db.query(Employee).filter_by(id=record.employee_id).first()
    recipient = db.query(User).filter_by(id=employee.user_id).first() if employee else None
    if recipient:
        create_in_app_notification(db, user_id=recipient.id, category="payroll", title="Salary credit recorded",
            message=f"Salary credit simulation recorded for {record.pay_period}. Amount: INR {Decimal(record.net_salary):,.2f}.",
            source_type="payroll_record", source_id=record.id, created_by=actor.id)
    db.commit(); db.refresh(record)
    return _payload(db, record)


@router.get("/me", response_model=list[PayrollResponse])
def my_payroll(db: Db, user: CurrentUser):
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not employee: raise HTTPException(status_code=404, detail="Employee record not found.")
    rows = db.query(PayrollRecord).filter(PayrollRecord.employee_id == employee.id).order_by(PayrollRecord.pay_period.desc()).all()
    return [_payload(db, record) for record in rows]


@router.get("/notifications")
def notification_history(db: Db, actor: HrUser, limit: int = Query(100, ge=1, le=500)):
    rows = db.query(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(limit).all()
    return [{"id": row.id, "recipient": row.recipient, "template_key": row.template_key, "subject": row.subject,
        "status": row.status, "error_message": row.error_message, "related_entity_type": row.related_entity_type,
        "related_entity_id": row.related_entity_id, "created_at": row.created_at} for row in rows]


def _make_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    story = [Paragraph("PeopleDesk — Salary Slip", styles["Title"]), Spacer(1, 8),
        Paragraph(f"Pay period: <b>{escape(str(data['pay_period']))}</b>", styles["Normal"]), Spacer(1, 14),
        Paragraph("Employee Details", styles["Heading2"])]
    employee_rows = [["Employee", escape(str(data["employee_name"]))], ["Employee code", escape(str(data["employee_code"]))],
        ["Department", escape(str(data["department"]))], ["Designation", escape(str(data["designation"]))], ["Email", escape(str(data["email"]))]]
    story.append(Table(employee_rows, colWidths=[130, 330], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf1ff")), ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#24324a")),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#dce3ef")), ("PADDING", (0, 0), (-1, -1), 8)])))
    story += [Spacer(1, 18), Paragraph("Salary Breakdown", styles["Heading2"])]
    money = lambda value: f"INR {Decimal(value):,.2f}"
    salary_rows = [["Component", "Amount"], ["Base salary (monthly gross base)", money(data["base_salary"])], ["Basic pay (included in base salary)", money(data.get("basic_pay", 0))],
        ["Allowances", money(data["allowances"])], ["Bonus", money(data.get("bonus", 0))], ["Variable pay", money(data.get("variable_pay", 0))],
        ["Overtime hours", str(data.get("overtime_hours", 0))], ["Overtime pay", money(data.get("overtime_pay", 0))]]
    for component in data.get("component_breakdown", []):
        if component.get("code") in {"BASIC_PAY", "ALLOWANCES", "BONUS", "VARIABLE_PAY", "OVERTIME", "OTHER_DEDUCTIONS"}:
            continue
        comp_type = component.get("component_type")
        amount = money(component.get("amount", 0))
        if comp_type == "deduction": amount = f"- {amount}"
        salary_rows.append([escape(str(component.get("name", "Salary component"))), amount])
    salary_rows += [["Other deductions", f"- {money(data['deductions'])}"], ["Configured deductions", f"- {money(data.get('component_deduction_total', 0))}"],
        ["LOP days", str(data.get("lop_days", 0))], ["LOP deduction", f"- {money(data.get('lop_deduction', 0))}"],
        ["Attendance days", str(data.get("attendance_days", 0))], ["Paid leave days", str(data.get("paid_leave_days", 0))],
        ["Manual adjustment", money(data["adjustment_amount"])]]
    if data.get("adjustment_note"): salary_rows.append(["Adjustment note", escape(str(data["adjustment_note"]))])
    salary_rows.append(["NET SALARY", money(data["net_salary"])])
    story.append(Table(salary_rows, colWidths=[270, 190], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263f8f")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e7f8ef")), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#dce3ef")), ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 9)])))
    story += [Spacer(1, 20), Paragraph("This is a system-generated salary slip. Salary credit status is simulated in this application; no bank transfer is made.", styles["Italic"])]
    document.build(story)
    return buffer.getvalue()


@router.get("/{record_id}/salary-slip.pdf")
def download_salary_slip(record_id: int, db: Db, user: CurrentUser):
    record = db.query(PayrollRecord).filter(PayrollRecord.id == record_id).first()
    if not record: raise HTTPException(status_code=404, detail="Salary slip not found.")
    employee = db.query(Employee).filter(Employee.id == record.employee_id).first()
    if user.role not in {"admin", "hr"} and (not employee or employee.user_id != user.id):
        raise HTTPException(status_code=403, detail="You can only download your own salary slips.")
    data = _payload(db, record)
    write_audit_log(db, actor_user_id=user.id, action="payroll.salary_slip_downloaded", entity_type="payroll_record",
                    entity_id=record.id, details={"pay_period": record.pay_period})
    db.commit()
    pdf = _make_pdf(data)
    safe_period = record.pay_period.replace("-", "_")
    return StreamingResponse(BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="salary_slip_{data["employee_code"]}_{safe_period}.pdf"'})
