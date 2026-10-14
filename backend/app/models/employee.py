from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )

    employee_code = Column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )

    department = Column(String(100), nullable=False)
    designation = Column(String(100), nullable=False)

    phone = Column(String(20), nullable=True)
    monthly_salary = Column(Numeric(12, 2), nullable=False, default=0)

    joining_date = Column(Date, nullable=False)

    employment_status = Column(
        String(20),
        nullable=False,
        default="active",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )