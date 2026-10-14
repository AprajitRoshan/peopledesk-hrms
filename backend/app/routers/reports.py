import csv
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from typing import Annotated
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
from sqlalchemy.orm import Session
from app.core.dependencies import require_admin_or_hr
from app.database import get_db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.leave_request import LeaveRequest
from app.models.payroll import PayrollRecord
from app.models.user import User

router = APIRouter(prefix="/api/reports", tags=["Reports and Analytics"])
Db = Annotated[Session, Depends(get_db)]
HrUser = Annotated[User, Depends(require_admin_or_hr)]


def _date_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    today = date.today()
    start = start_date or today.replace(day=1)
    end = end_date or today
    if end < start:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")
    return start, end


def _hours(record: Attendance) -> str:
    if not record.check_in or not record.check_out: return ""
    return f"{max(0, (record.check_out - record.check_in).total_seconds() / 3600):.2f}"


def _attendance_data(db: Session, start: date, end: date, department: str | None):
    query = db.query(Attendance, Employee, User).join(Employee, Employee.id == Attendance.employee_id).join(User, User.id == Employee.user_id)
    query = query.filter(Attendance.work_date >= start, Attendance.work_date <= end)
    if department: query = query.filter(Employee.department == department)
    rows = query.order_by(Attendance.work_date.desc(), Employee.employee_code).limit(10000).all()
    header = ["Employee code", "Employee name", "Department", "Work date", "Check in", "Check out", "Worked hours", "Status", "Correction note"]
    data = [[e.employee_code, u.full_name, e.department, a.work_date.isoformat(), str(a.check_in or ""), str(a.check_out or ""),
             _hours(a), a.status, a.correction_note or ""] for a, e, u in rows]
    return header, data


def _leave_data(db: Session, start: date, end: date, department: str | None):
    query = db.query(LeaveRequest, Employee, User).join(Employee, Employee.id == LeaveRequest.employee_id).join(User, User.id == Employee.user_id)
    query = query.filter(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)
    if department: query = query.filter(Employee.department == department)
    rows = query.order_by(LeaveRequest.created_at.desc()).limit(10000).all()
    header = ["Employee code", "Employee name", "Department", "Leave type", "Start date", "End date", "Status", "Reason", "Review note"]
    data = [[e.employee_code, u.full_name, e.department, l.leave_type, l.start_date.isoformat(), l.end_date.isoformat(),
             l.status, l.reason, l.review_note or ""] for l, e, u in rows]
    return header, data


def _payroll_data(db: Session, period: str | None, department: str | None):
    query = db.query(PayrollRecord, Employee, User).join(Employee, Employee.id == PayrollRecord.employee_id).join(User, User.id == Employee.user_id)
    if period: query = query.filter(PayrollRecord.pay_period == period)
    if department: query = query.filter(Employee.department == department)
    rows = query.order_by(PayrollRecord.pay_period.desc(), Employee.employee_code).limit(10000).all()
    header = ["Employee code", "Employee name", "Department", "Pay period", "Base salary", "Allowances", "Other deductions", "LOP days", "LOP deduction", "Adjustment", "Net salary", "Status"]
    data = [[e.employee_code, u.full_name, e.department, p.pay_period, str(p.base_salary), str(p.allowances), str(p.deductions),
             p.lop_days, str(p.lop_deduction), str(p.adjustment_amount), str(p.net_salary), p.status] for p, e, u in rows]
    return header, data


def _csv_response(filename: str, header: list[str], rows: list[list]):
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header); writer.writerows(rows)
    data = buffer.getvalue().encode("utf-8-sig")
    return StreamingResponse(BytesIO(data), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})


def _pdf_response(filename: str, title: str, header: list[str], rows: list[list]):
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 10)]
    normalized = [[Paragraph(escape(str(v)), styles["BodyText"]) for v in row] for row in rows]
    wrapped_header = [Paragraph(f"<b>{escape(str(value))}</b>", styles["BodyText"]) for value in header]
    usable_width = landscape(A4)[0] - 48
    column_widths = [usable_width / max(1, len(header))] * len(header)
    table = LongTable([wrapped_header, *normalized], colWidths=column_widths, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263f8f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#d4dbe7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("LEADING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fb")]),
    ]))
    story.append(table)
    document.build(story)
    return StreamingResponse(BytesIO(buffer.getvalue()), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})


@router.get("/summary")
def report_summary(db: Db, actor: HrUser, start_date: date | None = None, end_date: date | None = None,
                   department: str | None = Query(None, max_length=100), period: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    start, end = _date_range(start_date, end_date)
    a_query = db.query(Attendance).join(Employee, Employee.id == Attendance.employee_id).filter(Attendance.work_date >= start, Attendance.work_date <= end)
    l_query = db.query(LeaveRequest).join(Employee, Employee.id == LeaveRequest.employee_id).filter(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)
    p_query = db.query(PayrollRecord).join(Employee, Employee.id == PayrollRecord.employee_id)
    if department:
        a_query = a_query.filter(Employee.department == department); l_query = l_query.filter(Employee.department == department); p_query = p_query.filter(Employee.department == department)
    if period: p_query = p_query.filter(PayrollRecord.pay_period == period)
    return {"start_date": start, "end_date": end, "department": department, "pay_period": period,
        "attendance_records": a_query.count(), "leave_requests": l_query.count(),
        "pending_leaves": l_query.filter(LeaveRequest.status == "pending").count(),
        "approved_leaves": l_query.filter(LeaveRequest.status == "approved").count(),
        "payroll_records": p_query.count(), "net_payroll_total": str(sum((row.net_salary for row in p_query.all()), Decimal("0.00")))}


@router.get("/attendance.csv")
def attendance_csv(db: Db, actor: HrUser, start_date: date | None = None, end_date: date | None = None,
                   department: str | None = Query(None, max_length=100)):
    start, end = _date_range(start_date, end_date); header, rows = _attendance_data(db, start, end, department)
    return _csv_response(f"attendance_report_{start}_{end}", header, rows)


@router.get("/attendance.pdf")
def attendance_pdf(db: Db, actor: HrUser, start_date: date | None = None, end_date: date | None = None,
                   department: str | None = Query(None, max_length=100)):
    start, end = _date_range(start_date, end_date); header, rows = _attendance_data(db, start, end, department)
    return _pdf_response(f"attendance_report_{start}_{end}", f"Attendance Report: {start} to {end}", header, rows)


@router.get("/leaves.csv")
def leaves_csv(db: Db, actor: HrUser, start_date: date | None = None, end_date: date | None = None,
               department: str | None = Query(None, max_length=100)):
    start, end = _date_range(start_date, end_date); header, rows = _leave_data(db, start, end, department)
    return _csv_response(f"leave_report_{start}_{end}", header, rows)


@router.get("/leaves.pdf")
def leaves_pdf(db: Db, actor: HrUser, start_date: date | None = None, end_date: date | None = None,
               department: str | None = Query(None, max_length=100)):
    start, end = _date_range(start_date, end_date); header, rows = _leave_data(db, start, end, department)
    return _pdf_response(f"leave_report_{start}_{end}", f"Leave Report: {start} to {end}", header, rows)


@router.get("/payroll.csv")
def payroll_csv(db: Db, actor: HrUser, period: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                department: str | None = Query(None, max_length=100)):
    header, rows = _payroll_data(db, period, department)
    return _csv_response(f"payroll_report_{period or 'all_periods'}", header, rows)


@router.get("/payroll.pdf")
def payroll_pdf(db: Db, actor: HrUser, period: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                department: str | None = Query(None, max_length=100)):
    header, rows = _payroll_data(db, period, department)
    return _pdf_response(f"payroll_report_{period or 'all_periods'}", f"Payroll Summary: {period or 'All periods'}", header, rows)
