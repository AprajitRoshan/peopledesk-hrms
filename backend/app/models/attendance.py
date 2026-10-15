from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from app.database import Base


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_day"),)

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="present")
    correction_note = Column(String(500), nullable=True)
    shift_id = Column(Integer, ForeignKey("work_shifts.id", ondelete="SET NULL"), nullable=True, index=True)
    late_minutes = Column(Integer, nullable=False, default=0)
    early_leave_minutes = Column(Integer, nullable=False, default=0)
    overtime_minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
