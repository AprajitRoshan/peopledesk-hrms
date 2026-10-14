from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.database import Base, engine, ensure_compatibility_columns
# Import all models so SQLAlchemy registers the complete Day 1 schema.
from app.models import User, Employee, Attendance, LeaveRequest, AuditLog, PayrollRecord, NotificationLog, LeaveBalance, EmployeeDocument  # noqa: F401
from app.routers.auth import router as auth_router
from app.routers.employees import router as employees_router
from app.routers.attendance import router as attendance_router
from app.routers.leaves import router as leaves_router
from app.routers.dashboard import router as dashboard_router
from app.routers.audit import router as audit_router
from app.routers.payroll import router as payroll_router
from app.routers.documents import router as documents_router
from app.routers.admin import router as admin_router
from app.routers.reports import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates missing tables only; it does not migrate existing table schemas.
    Base.metadata.create_all(bind=engine)
    ensure_compatibility_columns()
    yield


app = FastAPI(title=settings.app_name, description="Human Resource Management System API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url, "http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(attendance_router)
app.include_router(leaves_router)
app.include_router(dashboard_router)
app.include_router(audit_router)
app.include_router(payroll_router)
app.include_router(documents_router)
app.include_router(admin_router)
app.include_router(reports_router)


@app.get("/")
def root():
    return {"message": "HRMS API is running", "documentation": "/docs"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "HRMS API"}


@app.get("/api/health/db")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database connection failed; check local environment settings.") from exc
