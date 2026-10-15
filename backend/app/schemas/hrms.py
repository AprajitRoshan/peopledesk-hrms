from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, computed_field


class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    work_date: date
    check_in: datetime | None
    check_out: datetime | None
    status: str
    correction_note: str | None = None
    shift_id: int | None = None
    late_minutes: int = 0
    early_leave_minutes: int = 0
    overtime_minutes: int = 0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def worked_hours(self) -> float | None:
        if self.check_in is None or self.check_out is None:
            return None
        return round(max(0.0, (self.check_out - self.check_in).total_seconds() / 3600), 2)


class LeaveCreate(BaseModel):
    start_date: date
    end_date: date
    leave_type: Literal["annual", "sick", "personal", "unpaid"] = "annual"
    reason: str = Field(min_length=5, max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    review_note: str | None = Field(default=None, max_length=1000)


class LeaveResponse(BaseModel):
    id: int
    employee_id: int
    start_date: date
    end_date: date
    leave_type: str
    reason: str
    status: str
    review_note: str | None = None
    days_requested: int = 0
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime
    employee_name: str | None = None
    employee_code: str | None = None
    model_config = ConfigDict(from_attributes=True)


class AdminDashboardResponse(BaseModel):
    employee_count: int
    active_employee_count: int
    checked_in_today: int
    pending_leave_requests: int
    payroll_status: str = "Payroll module active"


class EmployeeDashboardResponse(BaseModel):
    full_name: str
    employee_code: str
    department: str
    designation: str
    monthly_salary: float = 0
    attendance_today: AttendanceResponse | None
    pending_leave_requests: int
