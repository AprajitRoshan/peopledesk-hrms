from pathlib import Path
from uuid import uuid4
from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.audit import write_audit_log
from app.core.dependencies import get_current_user, require_admin_or_hr
from app.database import get_db
from app.models.employee import Employee
from app.models.employee_document import EmployeeDocument
from app.models.user import User

router = APIRouter(prefix="/api/documents", tags=["Employee Documents"])
Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
HrUser = Annotated[User, Depends(require_admin_or_hr)]
STORAGE = Path(__file__).resolve().parents[2] / "storage" / "employee_documents"
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_TYPES = {".pdf": {"application/pdf"}, ".png": {"image/png"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}}


def _employee_for_user(db: Session, user: User) -> Employee:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if employee is None: raise HTTPException(status_code=404, detail="Employee record not found.")
    return employee


def _payload(row: EmployeeDocument) -> dict:
    return {"id": row.id, "employee_id": row.employee_id, "original_filename": row.original_filename,
            "content_type": row.content_type, "file_size": row.file_size, "uploaded_by": row.uploaded_by,
            "created_at": row.created_at}


@router.get("/me")
def my_documents(db: Db, user: CurrentUser):
    employee = _employee_for_user(db, user)
    rows = db.query(EmployeeDocument).filter(EmployeeDocument.employee_id == employee.id).order_by(EmployeeDocument.created_at.desc()).all()
    return [_payload(row) for row in rows]


@router.get("/{employee_id}")
def list_employee_documents(employee_id: int, db: Db, user: CurrentUser):
    if user.role not in {"admin", "hr"}:
        employee = _employee_for_user(db, user)
        if employee.id != employee_id: raise HTTPException(status_code=403, detail="You can only view your own documents.")
    if not db.query(Employee.id).filter(Employee.id == employee_id).first():
        raise HTTPException(status_code=404, detail="Employee not found.")
    rows = db.query(EmployeeDocument).filter(EmployeeDocument.employee_id == employee_id).order_by(EmployeeDocument.created_at.desc()).all()
    return [_payload(row) for row in rows]


@router.post("/{employee_id}", status_code=201)
async def upload_employee_document(employee_id: int, db: Db, user: CurrentUser, file: UploadFile = File(...)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None: raise HTTPException(status_code=404, detail="Employee not found.")
    if user.role not in {"admin", "hr"} and employee.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only upload documents to your own profile.")
    original = Path(file.filename or "document").name[:255]
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF, PNG, and JPEG documents are accepted.")
    if file.content_type not in ALLOWED_TYPES[extension]:
        raise HTTPException(status_code=415, detail="The file content type does not match its extension.")
    contents = await file.read(MAX_BYTES + 1)
    if not contents: raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    if len(contents) > MAX_BYTES: raise HTTPException(status_code=413, detail="Maximum document size is 5 MB.")
    if extension == ".pdf" and not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file does not have a valid PDF signature.")
    if extension == ".png" and not contents.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="The uploaded file does not have a valid PNG signature.")
    if extension in {".jpg", ".jpeg"} and not contents.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="The uploaded file does not have a valid JPEG signature.")
    STORAGE.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid4().hex}{extension}"
    (STORAGE / storage_key).write_bytes(contents)
    row = EmployeeDocument(employee_id=employee.id, original_filename=original, storage_key=storage_key,
        content_type=file.content_type, file_size=len(contents), uploaded_by=user.id)
    db.add(row); db.flush()
    write_audit_log(db, actor_user_id=user.id, action="employee.document_uploaded", entity_type="employee_document",
                    entity_id=row.id, details={"employee_id": employee.id, "filename": original, "file_size": len(contents)})
    db.commit(); db.refresh(row)
    return _payload(row)


@router.get("/file/{document_id}")
def download_document(document_id: int, db: Db, user: CurrentUser):
    row = db.query(EmployeeDocument).filter(EmployeeDocument.id == document_id).first()
    if not row: raise HTTPException(status_code=404, detail="Document not found.")
    if user.role not in {"admin", "hr"}:
        employee = _employee_for_user(db, user)
        if employee.id != row.employee_id: raise HTTPException(status_code=403, detail="You can only download your own documents.")
    path = (STORAGE / row.storage_key).resolve()
    if not path.is_relative_to(STORAGE.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Document file is missing from storage.")
    return FileResponse(path, media_type=row.content_type, filename=row.original_filename)
