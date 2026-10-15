from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmployeeCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    employee_code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    department: str = Field(min_length=2, max_length=100)
    designation: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    region: str | None = Field(default=None, max_length=100)
    joining_date: date
    monthly_salary: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)

    @field_validator("full_name", "department", "designation")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class EmployeeResponse(BaseModel):
    id: int
    user_id: int
    employee_code: str
    department: str
    designation: str
    phone: str | None
    region: str | None = None
    joining_date: date
    employment_status: str
    monthly_salary: Decimal = Decimal("0.00")
    created_at: datetime
    full_name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    department: str | None = Field(default=None, min_length=2, max_length=100)
    designation: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    region: str | None = Field(default=None, max_length=100)
    joining_date: date | None = None
    monthly_salary: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    employment_status: Literal["active", "inactive"] | None = None

    @field_validator("full_name", "department", "designation")
    @classmethod
    def non_blank_optional(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value
