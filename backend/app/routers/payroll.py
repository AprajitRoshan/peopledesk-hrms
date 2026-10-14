from calendar import monthrange
from datetime import date, datetime
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


def _weekdays(start: date, end: date) -> int:
    if end < start:
        return 0
    return sum(1 for offset in range((end - start).days + 1) if date.fromordinal(start.toordinal() + offset).weekday() < 5)


def _approved_leave_days(db: Session, employee_id: int, first: date, last: date, leave_types: set[str]) -> int:
    rows = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == "approved", LeaveRequest.leave_type.in_(leave_types),
        LeaveRequest.start_date <= last, LeaveRequest.end_date >= first).all()
    total = 0
    for leave in rows:
        overlap_start, overlap_end = max(first, leave.start_date), min(last, leave.end_date)
        total += _weekdays(overlap_start, overlap_end)
    return total


def _payroll_facts(db: Session, employee_id: int, period: str, base_salary: Decimal) -> dict:
    first, last, _ = _period_dates(period)
    attendance_days = db.query(Attendance.id).filter(Attendance.employee_id == employee_id,
        Attendance.work_date >= first, Attendance.work_date <= last,
        Attendance.check_in.isnot(None), Attendance.status == "present").count()
    paid_leave_days = _approved_leave_days(db, employee_id, first, last, {"annual", "sick", "personal"})
    unpaid_rows = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == "approved", LeaveRequest.leave_type == "unpaid",
        LeaveRequest.start_date <= last, LeaveRequest.end_date >= first).all()
    lop_dates = set()
    for leave in unpaid_rows:
        overlap_start, overlap_end = max(first, leave.start_date), min(last, leave.end_date)
        for offset in range((overlap_end - overlap_start).days + 1):
            day = overlap_start.fromordinal(overlap_start.toordinal() + offset)
            if day.weekday() < 5: lop_dates.add(day)
    absent_rows = db.query(Attendance.work_date).filter(Attendance.employee_id == employee_id,
        Attendance.work_date >= first, Attendance.work_date <= last, Attendance.status == "absent").all()
    lop_dates.update(row[0] for row in absent_rows if row[0].weekday() < 5)
    lop_days = len(lop_dates)
    workdays = _weekdays(first, last)
    lop_deduction = ((base_salary / Decimal(max(workdays, 1))) * Decimal(lop_days)).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"attendance_days": attendance_days, "paid_leave_days": paid_leave_days,
            "lop_days": lop_days, "lop_deduction": lop_deduction}


def _payload_joined(record: PayrollRecord, employee: Employee, user: User) -> dict:
    return {"id": record.id, "employee_id": record.employee_id, "employee_code": employee.employee_code,
        "employee_name": user.full_name, "email": user.email, "department": employee.department,
        "designation": employee.designation, "pay_period": record.pay_period, "base_salary": record.base_salary,
        "allowances": record.allowances, "deductions": record.deductions,
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


@router.post("", response_model=PayrollResponse, status_code=201)
def process_payroll(payload: PayrollCreate, db: Db, actor: HrUser):
    employee = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.employment_status == "active").first()
    if not employee: raise HTTPException(status_code=404, detail="Active employee not found.")
    if db.query(PayrollRecord.id).filter(PayrollRecord.employee_id == employee.id, PayrollRecord.pay_period == payload.pay_period).first():
        raise HTTPException(status_code=409, detail="Payroll already exists for this employee and period. Duplicate processing is blocked.")
    base_salary = payload.base_salary if payload.base_salary is not None else Decimal(employee.monthly_salary or 0)
    if base_salary <= 0:
        raise HTTPException(status_code=422, detail="Set the employee's monthly salary or provide a base salary before processing payroll.")
    facts = _payroll_facts(db, employee.id, payload.pay_period, base_salary)
    net_salary = (base_salary + payload.allowances + payload.adjustment_amount - payload.deductions - facts["lop_deduction"]).quantize(CENT, rounding=ROUND_HALF_UP)
    if net_salary < 0: raise HTTPException(status_code=422, detail="Net salary cannot be negative after LOP deduction.")
    record = PayrollRecord(employee_id=employee.id, pay_period=payload.pay_period, base_salary=base_salary,
        allowances=payload.allowances, deductions=payload.deductions, adjustment_amount=payload.adjustment_amount,
        adjustment_note=payload.adjustment_note.strip() if payload.adjustment_note else None,
        attendance_days=facts["attendance_days"], paid_leave_days=facts["paid_leave_days"],
        lop_days=facts["lop_days"], lop_deduction=facts["lop_deduction"],
        net_salary=net_salary, status="processed", processed_by=actor.id)
    try:
        db.add(record); db.flush()
        user = db.query(User).filter(User.id == employee.user_id).first()
        details = {"employee_id": employee.id, "period": payload.pay_period, "net_salary": str(net_salary),
                   "attendance_days": facts["attendance_days"], "paid_leave_days": facts["paid_leave_days"],
                   "lop_days": facts["lop_days"], "lop_deduction": str(facts["lop_deduction"])}
        write_audit_log(db, actor_user_id=actor.id, action="payroll.processed", entity_type="payroll_record", entity_id=record.id, details=details)
        if user:
            send_template_notification(db, recipient=user.email, template_key="payroll_processed",
                context={"name": user.full_name, "period": payload.pay_period}, related_entity_type="payroll_record", related_entity_id=record.id)
            send_template_notification(db, recipient=user.email, template_key="salary_slip_generated",
                context={"name": user.full_name, "period": payload.pay_period}, related_entity_type="payroll_record", related_entity_id=record.id)
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
    net_salary = (record.base_salary + record.allowances + payload.adjustment_amount - record.deductions - record.lop_deduction).quantize(CENT, rounding=ROUND_HALF_UP)
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
    salary_rows = [["Component", "Amount"], ["Base salary", money(data["base_salary"])], ["Allowances", money(data["allowances"])],
        ["Other deductions", f"- {money(data['deductions'])}"], ["LOP days", str(data.get("lop_days", 0))],
        ["LOP deduction", f"- {money(data.get('lop_deduction', 0))}"],
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
