from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, Boolean, UniqueConstraint, func
from app.database import Base

class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    holiday_date = Column(Date, nullable=False, index=True)
    holiday_type = Column(String(20), nullable=False, default="company", index=True)  # company, regional, optional
    region = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

class OptionalHolidaySelection(Base):
    __tablename__ = "optional_holiday_selections"
    __table_args__ = (UniqueConstraint("holiday_id", "employee_id", name="uq_optional_holiday_employee"),)
    id = Column(Integer, primary_key=True, index=True)
    holiday_id = Column(Integer, ForeignKey("holidays.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_at = Column(DateTime, server_default=func.now(), nullable=False)
