from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from app.database import Base


class LeaveBalance(Base):
    __tablename__ = "leave_balances"
    __table_args__ = (UniqueConstraint("employee_id", "leave_type", name="uq_leave_balance_employee_type"),)

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type = Column(String(40), nullable=False)
    allocated_days = Column(Integer, nullable=False, default=0)
    used_days = Column(Integer, nullable=False, default=0)
