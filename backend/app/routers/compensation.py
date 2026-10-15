from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import require_admin_or_hr
from app.database import get_db
from app.models.compensation import CompensationRevision, SalaryComponent
from app.models.employee import Employee
from app.models.user import User

router = APIRouter(prefix="/api/compensation", tags=["Advanced Payroll & Compensation"])
Db = Annotated[Session, Depends(get_db)]
Hr = Annotated[User, Depends(require_admin_or_hr)]

class ComponentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    component_type: Literal["earning", "deduction"] = "earning"
    calculation_type: Literal["fixed", "percent_basic"] = "fixed"
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True
    @field_validator("name", "code")
    @classmethod
    def clean(cls, v):
        v=v.strip()
        if not v: raise ValueError("Value cannot be blank.")
        return v

class ComponentUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    component_type: Literal["earning", "deduction"] | None = None
    calculation_type: Literal["fixed", "percent_basic"] | None = None
    amount: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    is_active: bool | None = None

class RevisionCreate(BaseModel):
    employee_id: int = Field(gt=0)
    effective_from: date
    base_salary: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    basic_pay: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    allowances: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    bonus: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    variable_pay: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    other_deductions: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    overtime_multiplier: Decimal = Field(default=Decimal("1.5"), ge=1, le=5, max_digits=5, decimal_places=2)
    revision_note: str = Field(min_length=3, max_length=500)
    @model_validator(mode="after")
    def basic_valid(self):
        if self.basic_pay > self.base_salary:
            raise ValueError("Basic pay cannot exceed base salary.")
        if not self.revision_note.strip(): raise ValueError("A revision note is required for compensation history.")
        return self

def _component(row: SalaryComponent):
    return {"id": row.id, "name": row.name, "code": row.code, "component_type": row.component_type,
        "calculation_type": row.calculation_type, "amount": row.amount, "is_active": row.is_active, "created_at": row.created_at}

def _revision(db: Session, row: CompensationRevision):
    employee = db.query(Employee).filter_by(id=row.employee_id).first()
    user = db.query(User).filter_by(id=employee.user_id).first() if employee else None
    return {"id": row.id, "employee_id": row.employee_id, "employee_code": employee.employee_code if employee else None,
        "employee_name": user.full_name if user else None, "effective_from": row.effective_from, "effective_to": row.effective_to,
        "base_salary": row.base_salary, "basic_pay": row.basic_pay, "allowances": row.allowances, "bonus": row.bonus,
        "variable_pay": row.variable_pay, "other_deductions": row.other_deductions,
        "overtime_multiplier": row.overtime_multiplier, "revision_note": row.revision_note,
        "created_by": row.created_by, "created_at": row.created_at}

@router.get("/components")
def list_components(db: Db, actor: Hr, active_only: bool = False):
    q=db.query(SalaryComponent)
    if active_only: q=q.filter(SalaryComponent.is_active.is_(True))
    return [_component(r) for r in q.order_by(SalaryComponent.component_type, SalaryComponent.name).all()]

@router.post("/components", status_code=status.HTTP_201_CREATED)
def create_component(payload: ComponentCreate, db: Db, actor: Hr):
    if db.query(SalaryComponent.id).filter((SalaryComponent.code == payload.code) | (SalaryComponent.name == payload.name)).first():
        raise HTTPException(status_code=409, detail="A salary component with this name or code already exists.")
    row=SalaryComponent(**payload.model_dump(), created_by=actor.id); db.add(row); db.flush()
    write_audit_log(db, actor_user_id=actor.id, action="salary_component.created", entity_type="salary_component", entity_id=row.id,
                    details={"code": row.code, "type": row.component_type, "calculation_type": row.calculation_type})
    db.commit(); db.refresh(row); return _component(row)

@router.patch("/components/{component_id}")
def update_component(component_id: int, payload: ComponentUpdate, db: Db, actor: Hr):
    row=db.query(SalaryComponent).filter_by(id=component_id).first()
    if not row: raise HTTPException(status_code=404, detail="Salary component not found.")
    changes=payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Component name cannot be blank.")
    for k,v in changes.items(): setattr(row,k,v)
    write_audit_log(db, actor_user_id=actor.id, action="salary_component.updated", entity_type="salary_component", entity_id=row.id, details={"fields":list(changes)})
    db.commit(); db.refresh(row); return _component(row)

@router.get("/revisions")
def list_revisions(db: Db, actor: Hr, employee_id: int | None = Query(None, ge=1), limit: int = Query(500, ge=1, le=1000)):
    q=db.query(CompensationRevision)
    if employee_id: q=q.filter(CompensationRevision.employee_id == employee_id)
    return [_revision(db,r) for r in q.order_by(CompensationRevision.effective_from.desc(), CompensationRevision.id.desc()).limit(limit).all()]

@router.post("/revisions", status_code=status.HTTP_201_CREATED)
def create_revision(payload: RevisionCreate, db: Db, actor: Hr):
    employee = db.query(Employee).filter_by(id=payload.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found.")

    # If a revision already exists on this effective date, update that row in
    # place instead of forcing the user to create an invalid duplicate date.
    # This preserves one revision per employee/date and keeps the row's date
    # boundaries unchanged. The audit log retains the before/after values.
    same_date = db.query(CompensationRevision).filter(
        CompensationRevision.employee_id == employee.id,
        CompensationRevision.effective_from == payload.effective_from,
    ).first()
    if same_date:
        fields = (
            "base_salary", "basic_pay", "allowances", "bonus", "variable_pay",
            "other_deductions", "overtime_multiplier", "revision_note",
        )
        before = {field: str(getattr(same_date, field)) for field in fields}
        for field in fields:
            setattr(same_date, field, getattr(payload, field))
        db.flush()
        after = {field: str(getattr(same_date, field)) for field in fields}
        write_audit_log(
            db,
            actor_user_id=actor.id,
            action="compensation_revision.updated",
            entity_type="compensation_revision",
            entity_id=same_date.id,
            details={
                "employee_id": employee.id,
                "effective_from": same_date.effective_from.isoformat(),
                "previous_values": before,
                "updated_values": after,
            },
        )
        db.commit()
        db.refresh(same_date)
        return _revision(db, same_date)

    # New revisions must not be inserted before an already scheduled revision;
    # otherwise the effective-date history would become ambiguous.
    later = db.query(CompensationRevision.id).filter(
        CompensationRevision.employee_id == employee.id,
        CompensationRevision.effective_from > payload.effective_from,
    ).first()
    if later:
        raise HTTPException(
            status_code=409,
            detail="A later compensation revision already exists. Choose a date after the latest revision.",
        )

    previous = db.query(CompensationRevision).filter(
        CompensationRevision.employee_id == employee.id,
        CompensationRevision.effective_from < payload.effective_from,
        CompensationRevision.effective_to.is_(None),
    ).order_by(CompensationRevision.effective_from.desc()).first()
    if previous:
        # End dates are inclusive, so the new revision starts the next day.
        previous.effective_to = payload.effective_from - timedelta(days=1)
        db.flush()

    row = CompensationRevision(**payload.model_dump(), created_by=actor.id)
    db.add(row)
    db.flush()
    write_audit_log(
        db,
        actor_user_id=actor.id,
        action="compensation.revised",
        entity_type="compensation_revision",
        entity_id=row.id,
        details={
            "employee_id": employee.id,
            "effective_from": row.effective_from.isoformat(),
            "base_salary": str(row.base_salary),
            "revision_note": row.revision_note,
        },
    )
    db.commit()
    db.refresh(row)
    return _revision(db, row)
