from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


# Create the MySQL database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create database sessions
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

# Base class for all database models
Base = declarative_base()


# Dependency for database sessions
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

def ensure_compatibility_columns():
    """Small idempotent MySQL upgrades for existing local assignments.

    Base.metadata.create_all() creates new tables but does not add columns to
    tables that already exist. Keep this list explicit so existing Day 1 data
    remains intact when the Day 3 build starts.
    """
    from sqlalchemy import inspect

    required = {
        "employees": {
            "monthly_salary": "DECIMAL(12,2) NOT NULL DEFAULT 0",
        },
        "attendance": {
            "correction_note": "VARCHAR(500) NULL",
        },
        "leave_requests": {
            "review_note": "TEXT NULL",
        },
        "payroll_records": {
            "attendance_days": "INT NOT NULL DEFAULT 0",
            "paid_leave_days": "INT NOT NULL DEFAULT 0",
            "lop_days": "INT NOT NULL DEFAULT 0",
            "lop_deduction": "DECIMAL(12,2) NOT NULL DEFAULT 0",
            "locked_at": "DATETIME NULL",
            "credited_at": "DATETIME NULL",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in required.items():
            if not inspector.has_table(table_name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.exec_driver_sql(
                        f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {definition}"
                    )
                    existing.add(column_name)
