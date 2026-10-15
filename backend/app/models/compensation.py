from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from app.database import Base

class SalaryComponent(Base):
    __tablename__ = "salary_components"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    component_type = Column(String(15), nullable=False, default="earning")  # earning, deduction
    calculation_type = Column(String(20), nullable=False, default="fixed")  # fixed, percent_basic
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

class CompensationRevision(Base):
    __tablename__ = "compensation_revisions"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True, index=True)
    base_salary = Column(Numeric(12, 2), nullable=False)
    basic_pay = Column(Numeric(12, 2), nullable=False)
    allowances = Column(Numeric(12, 2), nullable=False, default=0)
    bonus = Column(Numeric(12, 2), nullable=False, default=0)
    variable_pay = Column(Numeric(12, 2), nullable=False, default=0)
    other_deductions = Column(Numeric(12, 2), nullable=False, default=0)
    overtime_multiplier = Column(Numeric(5, 2), nullable=False, default=1.5)
    revision_note = Column(String(500), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
