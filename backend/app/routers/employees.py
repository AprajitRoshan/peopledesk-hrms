from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.core.security import hash_password
from app.database import get_db
from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from app.models.user import User
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.notifications import send_template_notification

router = APIRouter(prefix="/api/employees", tags=["Employee Management"])
Db = Annotated[Session, Depends(get_db)]
HrUser = Annotated[User, Depends(require_admin_or_hr)]
CurrentUser = Annotated[User, Depends(get_current_user)]

DEFAULT_LEAVE_ALLOCATIONS = {"annual": 12, "sick": 10, "personal": 3}


def employee_payload(employee: Employee, user: User) -> dict:
    return {
        "id": employee.id, "user_id": employee.user_id,
        "employee_code": employee.employee_code, "department": employee.department,
        "designation": employee.designation, "phone": employee.phone, "region": employee.region,
        "joining_date": employee.joining_date, "employment_status": employee.employment_status,
        "monthly_salary": employee.monthly_salary, "created_at": employee.created_at,
        "full_name": user.full_name, "email": user.email,
    }


def _initialize_leave_balances(db: Session, employee_id: int) -> None:
    for leave_type, allocation in DEFAULT_LEAVE_ALLOCATIONS.items():
        existing = db.query(LeaveBalance).filter_by(employee_id=employee_id, leave_type=leave_type).first()
        if existing is None:
            db.add(LeaveBalance(employee_id=employee_id, leave_type=leave_type, allocated_days=allocation, used_days=0))


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, db: Db, actor: HrUser):
    email, code = str(payload.email).strip().lower(), payload.employee_code.strip()
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if db.query(Employee.id).filter(Employee.employee_code == code).first():
        raise HTTPException(status_code=409, detail="This employee code is already in use.")
    user = User(full_name=payload.full_name.strip(), email=email,
                password_hash=hash_password(payload.password), role="employee", is_active=True)
    try:
        db.add(user); db.flush()
        employee = Employee(user_id=user.id, employee_code=code,
            department=payload.department.strip(), designation=payload.designation.strip(),
            phone=payload.phone.strip() if payload.phone else None, region=payload.region.strip() if payload.region else None, joining_date=payload.joining_date,
            monthly_salary=payload.monthly_salary, employment_status="active")
        db.add(employee); db.flush()
        _initialize_leave_balances(db, employee.id)
        write_audit_log(db, actor_user_id=actor.id, action="employee.created", entity_type="employee", entity_id=employee.id,
                        details={"employee_code": code, "department": employee.department})
        send_template_notification(db, recipient=user.email, template_key="employee_onboarding",
            context={"name": user.full_name}, related_entity_type="employee", related_entity_id=employee.id)
        db.commit(); db.refresh(employee); db.refresh(user)
        return employee_payload(employee, user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Employee could not be created due to a data conflict.") from exc


@router.get("", response_model=list[EmployeeResponse])
def list_employees(db: Db, actor: HrUser, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                   department: str | None = Query(None, max_length=100), search: str | None = Query(None, max_length=100),
                   employment_status: str | None = Query(None, pattern="^(active|inactive)$")):
    query = db.query(Employee, User).join(User, User.id == Employee.user_id)
    if department: query = query.filter(Employee.department == department)
    if employment_status: query = query.filter(Employee.employment_status == employment_status)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter((User.full_name.ilike(term)) | (User.email.ilike(term)) | (Employee.employee_code.ilike(term)))
    rows = query.order_by(Employee.id.desc()).offset(skip).limit(limit).all()
    return [employee_payload(employee, user) for employee, user in rows]


@router.get("/me", response_model=EmployeeResponse)
def my_employee_record(db: Db, current_user: CurrentUser):
    row = db.query(Employee, User).join(User, User.id == Employee.user_id).filter(Employee.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee record not found.")
    return employee_payload(*row)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, payload: EmployeeUpdate, db: Db, actor: HrUser):
    row = db.query(Employee, User).join(User, User.id == Employee.user_id).filter(Employee.id == employee_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found.")
    employee, user = row
    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes and changes["email"] is not None:
        email = str(changes["email"]).strip().lower()
        if db.query(User.id).filter(User.email == email, User.id != user.id).first():
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        user.email = email
    if changes.get("employment_status") == "inactive" and user.role == "admin" and user.is_active:
        active_admins = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The system must retain at least one active administrator.")
    user_fields = {"full_name"}
    employee_fields = {"department", "designation", "phone", "region", "joining_date", "monthly_salary", "employment_status"}
    for field, value in changes.items():
        if field in user_fields and value is not None: setattr(user, field, value)
        elif field in employee_fields and value is not None: setattr(employee, field, value)
    if "employment_status" in changes:
        user.is_active = changes["employment_status"] == "active"
    write_audit_log(db, actor_user_id=actor.id, action="employee.updated", entity_type="employee", entity_id=employee.id,
                    details={"fields_changed": sorted(changes.keys())})
    try:
        db.commit(); db.refresh(employee); db.refresh(user)
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Employee update conflicts with existing data.") from exc
    return employee_payload(employee, user)


@router.delete("/{employee_id}")
def deactivate_employee(employee_id: int, db: Db, actor: HrUser):
    row = db.query(Employee, User).join(User, User.id == Employee.user_id).filter(Employee.id == employee_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found.")
    employee, user = row
    if user.role == "admin" and user.is_active:
        active_admins = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).count()
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The system must retain at least one active administrator.")
    employee.employment_status = "inactive"; user.is_active = False
    write_audit_log(db, actor_user_id=actor.id, action="employee.deactivated", entity_type="employee", entity_id=employee.id,
                    details={"employee_code": employee.employee_code})
    db.commit()
    return {"message": "Employee deactivated. Existing HR records have been retained.", "employee_id": employee.id}
