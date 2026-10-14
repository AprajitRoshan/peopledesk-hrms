# PeopleDesk HRMS — Final Full-Stack Build

A React + FastAPI + MySQL HRMS assignment project. This build continues the existing Day 1 and Day 2 code and adds the remaining reporting, role-management, attendance-correction, leave-balance, LOP, employee-document, payroll-locking, and salary-credit simulation workflows.

## Features mapped to the assignment

### Authentication and authorization
- JWT access-token authentication; token expiration is configured through `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Passwords are hashed with `pwdlib`/Argon2id; password hashes are never returned by APIs.
- Roles: `admin`, `hr`, and `employee`. Employees only see their own attendance, leave, documents, and payslips. Admin/HR manage workforce data; only Admin can change user roles and account access.
- The backend prevents removing or disabling the final active Admin.

### Employee management
- Create, search, update, and deactivate employee accounts without deleting historical HR records.
- Profile fields include employee code, department, designation, joining date, phone, and monthly base salary.
- Admin/HR can change salary and employment details; employee password hashes are not exposed.
- Secure employee document upload/download: PDF, PNG, JPEG; 5 MB maximum; random storage names; authenticated access; file-type/signature checks; upload audit records.

### Attendance and leave
- Employee check-in/check-out; one attendance record per employee and day; worked-hour calculation.
- Admin/HR monthly attendance summaries and correction/override workflow with a required reason and audit logging.
- Leave types: annual, sick, personal, unpaid. Paid leave balances initialize with annual 12 days, sick 10 days, and personal 3 days. These are demonstration defaults; adjust them to match your assignment/company policy.
- Leave approval validates available paid leave balance; weekends are not counted as leave days. Unpaid leave is treated as Loss of Pay (LOP).
- Leave history, review note, and notification log.

### Payroll and salary slips
- Payroll calculates net pay as `base salary + allowances + manual adjustment - other deductions - LOP deduction`.
- If base salary is omitted in the payroll request, the employee's profile monthly salary is used.
- LOP is based on approved unpaid leave weekdays and attendance records explicitly marked `absent`, deduplicated by date. Workdays are Monday–Friday; the demo does not account for public holidays, shift calendars, tax, PF, ESI, or other statutory calculations.
- Attendance days, paid leave days, LOP days, and LOP deduction are included in the payroll record and PDF slip.
- Duplicate employee/pay-period records are blocked. Admin/HR can apply a reasoned manual adjustment before payroll is locked.
- Payroll can be explicitly locked. Locked records cannot be adjusted. Salary credit is a simulation only, changes status to `credited`, and never sends a real payment.
- Employees download only their own PDF slips; Admin/HR can download all slips.

### Notification, reports, and audit
- Template-based onboarding, leave-application, leave-decision, payroll-processed, and salary-slip-generated notifications.
- If SMTP is not configured, notification attempts are recorded as `logged`. With SMTP configured, logs show `sent` or `failed`.
- Attendance, leave, and payroll report downloads in CSV and PDF with date/department filters where applicable.
- Timestamped audit logs for critical changes; there are no audit-log edit/delete endpoints.

## Folder structure

```text
hrms/
├── backend/
│   ├── app/
│   │   ├── core/            # Settings, JWT, dependencies, audit helper
│   │   ├── models/          # SQLAlchemy models
│   │   ├── routers/         # API routes by feature
│   │   ├── schemas/         # Pydantic validation/response schemas
│   │   └── services/        # Email notifications
│   ├── storage/             # Runtime employee documents (not committed)
│   ├── create_admin.py
│   └── requirements.txt
├── frontend/
│   └── src/features/        # Payroll, reports, attendance, roles, documents
├── database/                # Schema reference and database export script
├── postman/                 # Day 1, Day 2 and final Postman collections
└── submission/              # Evidence checklist and credential template
```

## Run locally on Windows

### 1. Database and environment

Keep your existing `backend/.env` and MySQL database. The source archive intentionally does not include the real `.env`, database password, JWT secret, virtual environment, or runtime uploaded documents.

If starting from a clean database, create the database and run `database/hrms_schema.sql`. For your existing `hrms_db`, the application creates missing tables and performs small idempotent column upgrades on startup; it does not drop existing data. Keep a backup before testing a new build.

Make sure `backend/.env` contains your existing MySQL values and a strong unique `JWT_SECRET_KEY`. If needed, generate a key from the `backend` directory:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The `.env.example` file lists all supported settings. Never commit `.env` to GitHub.

### 2. Backend

Open a VS Code terminal:

```powershell
cd D:\Stackly_training\hrms\backend
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Use your existing virtual environment and Admin account. Do not recreate the Admin if it already exists. FastAPI runs at `http://127.0.0.1:8000`; API docs at `/docs` are available for debugging individual endpoints.

### 3. Frontend

Open a second VS Code terminal:

```powershell
cd D:\Stackly_training\hrms\frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (typically `http://localhost:5173`). Sign in with your existing Admin. The admin/HR workspace has tabs for Overview, Employees, Attendance, Leave requests, Payroll, Reports, Documents, Notifications, Audit logs, and (Admin-only) Roles & users. Notifications and audit events are read-only views of backend logs. The Notifications tab calls `GET /api/payroll/notifications` and distinguishes `sent`, `logged` (SMTP not configured), and `failed` attempts. The employee workspace includes attendance, leave balances, leave history, salary slips, and employee documents.

### 4. SMTP (optional)

Fill `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `SMTP_USE_TLS` in `backend/.env`. Keep SMTP credentials local. Without SMTP, the app records notification attempts without sending email.

## Important API routes

| Area | Routes | Access |
|---|---|---|
| Authentication | `POST /api/auth/login`, `GET /api/auth/me` | Public login / authenticated profile |
| Employee | `/api/employees`, `/api/employees/{id}`, `/api/employees/me` | Admin/HR manage; employees self-view |
| Documents | `POST /api/documents/{employee_id}`, `GET /api/documents/me`, `GET /api/documents/file/{id}` | Admin/HR all; employee own |
| Attendance | `POST /api/attendance/check-in`, `/check-out`, `GET /api/attendance/me` | Employee own |
| Attendance admin | `GET /api/attendance`, `GET /api/attendance/summary`, `POST /api/attendance/override` | Admin/HR |
| Leave | `POST /api/leaves`, `GET /api/leaves/me`, `GET /api/leaves/balance/me` | Employee own |
| Leave admin | `GET /api/leaves`, `PATCH /api/leaves/{id}/decision`, `GET/PATCH /api/leaves/balance/...` | Admin/HR |
| Payroll | `POST /api/payroll`, `GET /api/payroll`, `GET /api/payroll/me` | Admin/HR all; employee own |
| Payroll actions | `PATCH /api/payroll/{id}/adjustment`, `POST /api/payroll/{id}/lock`, `POST /api/payroll/{id}/credit` | Admin/HR |
| Salary slip | `GET /api/payroll/{id}/salary-slip.pdf` | Admin/HR or record owner |
| Roles | `GET /api/admin/users`, `PATCH /api/admin/users/{id}/role`, `/status` | Admin only |
| Reports | `GET /api/reports/summary`, `/attendance.csv`, `/attendance.pdf`, `/leaves.csv`, `/leaves.pdf`, `/payroll.csv`, `/payroll.pdf` | Admin/HR |
| Notifications | `GET /api/payroll/notifications` | Admin/HR; read-only delivery log shown in the Notifications tab |
| Audit | `GET /api/audit-logs` | Admin/HR, read-only |

## Database export and final submission

- Import `postman/HRMS_Final.postman_collection.json` into Postman. Set `baseUrl`, sign in as Admin, then copy the employee access token for own-account requests.
- Export the real local database by running `database/export_database.ps1` from PowerShell. It prompts `mysqldump` for the MySQL password; do not place the password in the script or command history.
- Follow `submission/EVIDENCE_CHECKLIST.md` and copy `submission/CREDENTIALS_TEMPLATE.md` to a private file and fill it for the reviewer. Never commit the completed credentials file. Do not commit actual passwords or SMTP credentials into the public repository.
- Capture screenshots from the running app for Admin dashboard, Employee dashboard, Employee management, Attendance, Leave balance/approval, Payroll, PDF salary slip, Reports, Roles & users, and document upload/download. Screenshots provided during local testing are organized under `submission/local_evidence/`; capture only additional evidence for tests still pending.

## Validation notes and limitations

- The API schema has startup compatibility upgrades for the new Day 3 columns. A database backup is recommended before starting this version.
- The salary-credit state is demonstrative only; no payment gateway or bank transfer is connected.
- PDF/CSV reports are intended for the assignment dataset. For a production rollout, add background jobs, organization holiday/shift calendars, statutory payroll calculations, malware scanning, retention rules, migration management (e.g. Alembic), and deeper automated integration tests.
- Backend Python syntax, Postman JSON structure, and archive contents are checked during packaging. The Notification Log UI surfaces the existing `/api/payroll/notifications` endpoint. A full live MySQL/API integration test and production frontend build have not been completed in this environment; verify them locally on Windows using the commands above and complete `submission/EVIDENCE_CHECKLIST.md` before submitting.
