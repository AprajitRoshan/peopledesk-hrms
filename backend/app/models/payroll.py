from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from app.database import Base


class PayrollRecord(Base):
    __tablename__ = "payroll_records"
    __table_args__ = (UniqueConstraint("employee_id", "pay_period", name="uq_payroll_employee_period"),)

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    pay_period = Column(String(7), nullable=False, index=True)  # YYYY-MM
    base_salary = Column(Numeric(12, 2), nullable=False)
    basic_pay = Column(Numeric(12, 2), nullable=False, default=0)
    allowances = Column(Numeric(12, 2), nullable=False, default=0)
    bonus = Column(Numeric(12, 2), nullable=False, default=0)
    variable_pay = Column(Numeric(12, 2), nullable=False, default=0)
    overtime_hours = Column(Numeric(10, 2), nullable=False, default=0)
    overtime_pay = Column(Numeric(12, 2), nullable=False, default=0)
    component_breakdown = Column(Text, nullable=True)
    component_earning_total = Column(Numeric(12, 2), nullable=False, default=0)
    component_deduction_total = Column(Numeric(12, 2), nullable=False, default=0)
    deductions = Column(Numeric(12, 2), nullable=False, default=0)
    adjustment_amount = Column(Numeric(12, 2), nullable=False, default=0)
    adjustment_note = Column(String(500), nullable=True)
    attendance_days = Column(Integer, nullable=False, default=0)
    paid_leave_days = Column(Integer, nullable=False, default=0)
    lop_days = Column(Integer, nullable=False, default=0)
    lop_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    net_salary = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), nullable=False, default="processed")
    locked_at = Column(DateTime, nullable=True)
    credited_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processed_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
