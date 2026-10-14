from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.schemas.hrms import AdminDashboardResponse, EmployeeDashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/admin", response_model=AdminDashboardResponse)
def admin_dashboard(db: Db, admin: Annotated[User, Depends(require_admin_or_hr)]):
    today = date.today()
    employee_count = db.query(Employee).count()
    active_count = db.query(Employee).filter(Employee.employment_status == "active").count()
    checked_in = db.query(Attendance).filter(Attendance.work_date == today, Attendance.check_in.isnot(None)).count()
    pending = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()
    return AdminDashboardResponse(employee_count=employee_count, active_employee_count=active_count,
        checked_in_today=checked_in, pending_leave_requests=pending, payroll_status="Payroll module active")


@router.get("/employee", response_model=EmployeeDashboardResponse)
def employee_dashboard(db: Db, user: Annotated[User, Depends(get_current_user)]):
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee record not found.")
    attendance = db.query(Attendance).filter(Attendance.employee_id == employee.id, Attendance.work_date == date.today()).first()
    pending = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id, LeaveRequest.status == "pending").count()
    return EmployeeDashboardResponse(full_name=user.full_name, employee_code=employee.employee_code,
        department=employee.department, designation=employee.designation, monthly_salary=float(employee.monthly_salary or 0),
        attendance_today=attendance, pending_leave_requests=pending, payroll_status="Payroll module active")
