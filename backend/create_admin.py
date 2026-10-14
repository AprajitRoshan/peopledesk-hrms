from getpass import getpass
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User, Employee, Attendance, LeaveRequest, AuditLog, PayrollRecord, NotificationLog, LeaveBalance, EmployeeDocument  # noqa: F401


def main():
    Base.metadata.create_all(bind=engine)
    full_name = input("Admin full name: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass("Admin password (8-128 characters): ")
    confirmation = getpass("Confirm Admin password: ")
    if not full_name or len(full_name) > 150:
        print("Error: enter a valid name."); return
    if not email or len(email) > 255 or "@" not in email:
        print("Error: enter a valid email address."); return
    if len(password) < 8 or len(password) > 128:
        print("Error: password must be 8-128 characters."); return
    if password != confirmation:
        print("Error: passwords do not match."); return
    db = SessionLocal()
    try:
        if db.query(User.id).filter(User.email == email).first():
            print("An account with this email already exists."); return
        db.add(User(full_name=full_name, email=email, password_hash=hash_password(password), role="admin", is_active=True))
        db.commit()
        print("Admin account created successfully.")
        print(f"Admin email: {email}")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
