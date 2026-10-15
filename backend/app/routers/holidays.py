from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.employee import Employee
from app.models.holiday import Holiday, OptionalHolidaySelection
from app.models.user import User

router = APIRouter(prefix="/api/holidays", tags=["Holiday & Calendar Management"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
HrUser = Annotated[User, Depends(require_admin_or_hr)]

class HolidayCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    holiday_date: date
    holiday_type: Literal["company", "regional", "optional"] = "company"
    region: str | None = Field(None, max_length=100)
    department: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=2000)
    is_active: bool = True
    @field_validator("name")
    @classmethod
    def clean_name(cls, v):
        v = v.strip()
        if not v: raise ValueError("Holiday name cannot be blank.")
        return v
    @model_validator(mode="after")
    def scope(self):
        if self.holiday_type == "regional" and not (self.region or self.department):
            raise ValueError("Regional holidays require a region or department scope.")
        return self

class HolidayUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=160)
    holiday_date: date | None = None
    holiday_type: Literal["company", "regional", "optional"] | None = None
    region: str | None = Field(None, max_length=100)
    department: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=2000)
    is_active: bool | None = None


def _employee(db: Session, user: User) -> Employee | None:
    return db.query(Employee).filter(Employee.user_id == user.id).first()

def _payload(row: Holiday, employee: Employee | None, db: Session) -> dict:
    selected = False
    if employee and row.holiday_type == "optional":
        selected = db.query(OptionalHolidaySelection.id).filter_by(holiday_id=row.id, employee_id=employee.id).first() is not None
    return {"id": row.id, "name": row.name, "holiday_date": row.holiday_date, "holiday_type": row.holiday_type,
        "region": row.region, "department": row.department, "description": row.description, "is_active": row.is_active,
        "is_selected": selected, "created_at": row.created_at}

@router.get("")
def list_holidays(db: Db, user: CurrentUser, month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                  year: int | None = Query(None, ge=2000, le=2200), include_inactive: bool = False):
    employee = _employee(db, user)
    q = db.query(Holiday)
    if not include_inactive or user.role not in {"admin", "hr"}: q = q.filter(Holiday.is_active.is_(True))
    if month:
        y, m = map(int, month.split("-")); from calendar import monthrange
        q = q.filter(Holiday.holiday_date >= date(y, m, 1), Holiday.holiday_date <= date(y, m, monthrange(y, m)[1]))
    elif year:
        q = q.filter(Holiday.holiday_date >= date(year, 1, 1), Holiday.holiday_date <= date(year, 12, 31))
    if employee:
        q = q.filter((Holiday.department.is_(None)) | (Holiday.department == employee.department))
        q = q.filter((Holiday.region.is_(None)) | (Holiday.region == employee.region))
    return [_payload(row, employee, db) for row in q.order_by(Holiday.holiday_date.asc(), Holiday.name.asc()).limit(1000).all()]

@router.post("", status_code=status.HTTP_201_CREATED)
def create_holiday(payload: HolidayCreate, db: Db, actor: HrUser):
    row = Holiday(**payload.model_dump(), created_by=actor.id)
    db.add(row); db.flush()
    write_audit_log(db, actor_user_id=actor.id, action="holiday.created", entity_type="holiday", entity_id=row.id,
                    details={"name": row.name, "holiday_date": row.holiday_date.isoformat(), "holiday_type": row.holiday_type})
    db.commit(); db.refresh(row)
    return _payload(row, None, db)

@router.patch("/{holiday_id}")
def update_holiday(holiday_id: int, payload: HolidayUpdate, db: Db, actor: HrUser):
    row = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not row: raise HTTPException(status_code=404, detail="Holiday not found.")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Holiday name cannot be blank.")
    for key, value in changes.items(): setattr(row, key, value)
    if row.holiday_type == "regional" and not (row.region or row.department):
        raise HTTPException(status_code=422, detail="Regional holidays require a region or department scope.")
    write_audit_log(db, actor_user_id=actor.id, action="holiday.updated", entity_type="holiday", entity_id=row.id, details={"fields": list(changes)})
    db.commit(); db.refresh(row)
    return _payload(row, None, db)

@router.delete("/{holiday_id}")
def delete_holiday(holiday_id: int, db: Db, actor: HrUser):
    row = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not row: raise HTTPException(status_code=404, detail="Holiday not found.")
    # Keep references for the calendar history and disable rather than hard delete.
    row.is_active = False
    write_audit_log(db, actor_user_id=actor.id, action="holiday.deactivated", entity_type="holiday", entity_id=row.id, details={"name": row.name})
    db.commit()
    return {"message": "Holiday deactivated; historical record retained.", "id": holiday_id}

@router.post("/{holiday_id}/select")
def select_optional_holiday(holiday_id: int, db: Db, user: CurrentUser):
    row = db.query(Holiday).filter(Holiday.id == holiday_id, Holiday.is_active.is_(True)).first()
    if not row: raise HTTPException(status_code=404, detail="Holiday not found.")
    if row.holiday_type != "optional": raise HTTPException(status_code=422, detail="Only optional holidays can be selected.")
    employee = _employee(db, user)
    if not employee: raise HTTPException(status_code=404, detail="Employee profile not found.")
    if (row.department and row.department != employee.department) or (row.region and row.region != employee.region):
        raise HTTPException(status_code=404, detail="Holiday not found for this employee scope.")
    existing = db.query(OptionalHolidaySelection).filter_by(holiday_id=holiday_id, employee_id=employee.id).first()
    if existing: return {"message": "Optional holiday already selected.", "holiday_id": holiday_id}
    db.add(OptionalHolidaySelection(holiday_id=holiday_id, employee_id=employee.id))
    write_audit_log(db, actor_user_id=user.id, action="holiday.optional_selected", entity_type="holiday", entity_id=holiday_id, details={"employee_id": employee.id})
    db.commit()
    return {"message": "Optional holiday selected.", "holiday_id": holiday_id}

@router.delete("/{holiday_id}/select")
def deselect_optional_holiday(holiday_id: int, db: Db, user: CurrentUser):
    employee = _employee(db, user)
    if not employee: raise HTTPException(status_code=404, detail="Employee profile not found.")
    selection = db.query(OptionalHolidaySelection).filter_by(holiday_id=holiday_id, employee_id=employee.id).first()
    if selection:
        db.delete(selection); db.commit()
    return {"message": "Optional holiday selection removed.", "holiday_id": holiday_id}
