from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Time, Text, func
from app.database import Base

class WorkShift(Base):
    __tablename__ = "work_shifts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    shift_type = Column(String(20), nullable=False, default="general")  # general, night, flexible, remote
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    grace_minutes = Column(Integer, nullable=False, default=10)
    break_minutes = Column(Integer, nullable=False, default=0)
    overtime_after_minutes = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("work_shifts.id", ondelete="RESTRICT"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    effective_from = Column(Date, nullable=False, index=True)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
