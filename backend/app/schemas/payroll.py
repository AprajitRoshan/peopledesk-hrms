from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PayrollCreate(BaseModel):
    employee_id: int = Field(gt=0)
    pay_period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    base_salary: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    allowances: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    deductions: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    adjustment_amount: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    adjustment_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_net(self):
        if self.base_salary is not None and self.base_salary + self.allowances + self.adjustment_amount - self.deductions < 0:
            raise ValueError("Net salary cannot be negative.")
        if self.adjustment_amount != 0 and not (self.adjustment_note or "").strip():
            raise ValueError("Add a note when applying a manual salary adjustment.")
        return self


class PayrollResponse(BaseModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    email: str
    department: str
    designation: str
    pay_period: str
    base_salary: Decimal
    allowances: Decimal
    deductions: Decimal
    adjustment_amount: Decimal
    adjustment_note: str | None
    attendance_days: int = 0
    paid_leave_days: int = 0
    lop_days: int = 0
    lop_deduction: Decimal = Decimal("0.00")
    net_salary: Decimal
    status: str
    locked_at: datetime | None = None
    credited_at: datetime | None = None
    processed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PayrollAdjustment(BaseModel):
    adjustment_amount: Decimal = Field(max_digits=12, decimal_places=2)
    adjustment_note: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_adjustment(self):
        if not self.adjustment_note.strip():
            raise ValueError("Adjustment note cannot be blank.")
        return self
