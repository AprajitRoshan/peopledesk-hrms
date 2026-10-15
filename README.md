# PeopleDesk HRMS — Final Full-Stack Build

A React + FastAPI + MySQL HRMS assignment project. This build extends the existing PeopleDesk implementation with holiday/calendar management, user-scoped in-app notifications, shift scheduling, and advanced compensation while preserving the earlier employee, attendance, leave, payroll, reporting, documents, role management, email log, and audit features.

## Features mapped to the assignment

### Authentication and authorization
- JWT access-token authentication; token expiration is configured through `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Passwords are hashed with `pwdlib`/Argon2id; password hashes are never returned by APIs.
- Roles: `admin`, `hr`, and `employee`. Employees only see their own attendance, leave, documents, and payslips. Admin/HR manage workforce data; only Admin can change user roles and account access.
- The backend prevents removing or disabling the final active Admin.

### Employee management
- Create, search, update, and deactivate employee accounts without deleting historical HR records.
- Profile fields include employee code, department, designation, joining date, phone, region, and monthly base salary.
- Admin/HR can change salary and employment details; employee password hashes are not exposed.
- Secure employee document upload/download: PDF, PNG, JPEG; 5 MB maximum; random storage names; authenticated access; file-type/signature checks; upload audit records.

### Attendance and leave
- Employee check-in/check-out; one attendance record per employee and work date; worked-hour calculation.
- Admin/HR monthly attendance summaries and correction/override workflow with a required reason and audit logging.
- Holiday & calendar management: company-wide, region/department-scoped regional, and optional holidays. Admin/HR can maintain holidays; employees can view month/year calendars and select optional holidays.
- Holiday-aware workday calculations exclude applicable weekdays from leave-day, attendance expectation, and LOP calculations. Regional applicability uses the employee's region and department; optional holidays count only when selected by that employee.
- Shift scheduling: general, night, flexible, and remote shift definitions; employee- or department-level effective-dated assignments; assignment history; attendance report filters; late check-in, early checkout, and overtime metrics.
- Leave types: annual, sick, personal, unpaid. Paid leave balances initialize with annual 12 days, sick 10 days, and personal 3 days. These are demonstration defaults; adjust them to match company policy.
- Leave approval validates available paid leave balance; weekends and applicable holidays are not counted as leave days. Unpaid leave is treated as Loss of Pay (LOP).
- Leave history, review notes, email log, and in-app notifications on leave requests and decisions.

### Payroll and salary slips
- Advanced payroll supports base/basic pay, allowances, bonuses, variable pay, fixed or percent-of-basic components, configured deductions, shift-recorded overtime, manual adjustments, approved paid leave, and Loss of Pay (LOP).
- Net pay formula: `base salary + allowances + bonus + variable pay + configured earnings + overtime pay + manual adjustment - other deductions - configured deductions - LOP deduction`.
- If base salary is omitted, an effective compensation revision for the pay-period start date is used; otherwise the employee profile monthly salary is used. Compensation revisions retain historical effective dates.
- Configured salary components are evaluated when new payroll records are created. A `BASIC` or `BASIC_PAY` earning component sets the basic-pay breakdown and is not added twice to net pay.
- LOP uses approved unpaid leave weekdays and attendance records explicitly marked `absent`, deduplicated by date and excluding applicable holidays. The demonstration uses Monday–Friday workweeks and does not implement statutory tax, PF, ESI, or jurisdiction-specific payroll rules.
- Attendance days, paid leave days, LOP days/deduction, overtime hours/pay, bonus, variable pay, and configured components are included in the payroll record and generated salary slip.
- Duplicate employee/pay-period records are blocked. Admin/HR can apply a reasoned adjustment before payroll is locked. A locked record cannot be adjusted. Salary credit is simulated only; no bank transfer occurs.
- Employees download only their own PDF slips; Admin/HR can download all slips.

### Notification, reports, and audit
- Template-based onboarding, leave-application/decision, payroll-processed, and salary-slip-generated email notifications. SMTP attempts are recorded as `logged` when not configured, and `sent` or `failed` when sending is attempted.
- In-app notification center with per-user visibility, read/unread tracking, mark-read/read-all actions, category preferences, attendance/leave/payroll events, and Admin/HR broadcast announcements scoped to the organization or a department.
- Attendance, leave, and payroll report downloads in CSV and PDF with date/department filters where applicable; shift attendance reports include shift-wise late/early/overtime metrics.
- Timestamped audit logs for critical changes; the audit interface is read-only and exposes no edit/delete endpoint.

## Folder structure

```text
hrms/
├── backend/
│   ├── app/
│   │   ├── core/            # Settings, JWT, dependencies, audit helper
│   │   ├── models/          # SQLAlchemy models including holidays, shifts, compensation
│   │   ├── routers/         # API routes by feature
│   │   ├── schemas/         # Pydantic validation/response schemas
│   │   └── services/        # Email, in-app notifications, workforce calculations
│   ├── storage/             # Runtime employee documents (not committed)
│   ├── create_admin.py
│   └── requirements.txt
├── frontend/
│   └── src/features/        # Calendar, shifts, compensation, inbox, payroll, reports, documents
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

Open the Vite URL printed in the terminal (typically `http://localhost:5173`). Sign in with your existing Admin. Admin/HR workspace sections now include Overview, Employees, Attendance, Leave requests, Calendar, Shifts, Payroll, Compensation, Reports, Documents, Roles & users (Admin), In-app inbox, Email log, and Audit logs. Employees see their own shift, holiday calendar, in-app notifications/preferences, attendance/leave, salary slips, and documents. The Email log calls `GET /api/payroll/notifications`; `sent`, `logged`, and `failed` have distinct meanings.

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
| Holidays & calendar | `GET /api/holidays?month=YYYY-MM` or `?year=YYYY`, `POST /api/holidays`, `PATCH/DELETE /api/holidays/{id}`, `POST/DELETE /api/holidays/{id}/select` | Signed-in calendar readers; Admin/HR maintain holidays; employees select optional holidays |
| In-app notifications | `GET /api/in-app-notifications/me`, `PATCH /api/in-app-notifications/{id}/read`, `POST /api/in-app-notifications/read-all`, `GET/PATCH /api/in-app-notifications/preferences/me` | Authenticated user, own notifications/preferences only |
| Announcement broadcast | `POST /api/in-app-notifications/broadcast` | Admin/HR; whole organization or a department; recipient preferences are respected |
| Shifts | `GET/POST /api/shifts`, `PATCH /api/shifts/{id}`, `GET/POST /api/shifts/assignments`, `GET /api/shifts/me/current`, `GET /api/shifts/attendance-report` | Admin/HR manage; employee can view own assignment |
| Compensation | `GET/POST /api/compensation/components`, `PATCH /api/compensation/components/{id}`, `GET/POST /api/compensation/revisions` | Admin/HR |
| Notifications | `GET /api/payroll/notifications` | Admin/HR; read-only email delivery log |
| Audit | `GET /api/audit-logs` | Admin/HR, read-only |

## Database export and final submission

- The `postman/` folder contains Day 1, Day 2, and the consolidated 66-request final full-stack collection (including the Phase 3 holiday, inbox, shifts, and compensation routes). Postman Local Mode may store the final collection as a folder of `.request.yaml` definitions after upgrading to v3. Open `postman/HRMS — Final Full Stack Test Collection` and configure local credentials/tokens; never commit private environment/global values.
- Export the real local database by running `database/export_database.ps1` from PowerShell. It prompts `mysqldump` for the MySQL password; do not place the password in the script or command history.
- Follow `submission/EVIDENCE_CHECKLIST.md` and copy `submission/CREDENTIALS_TEMPLATE.md` to a private file and fill it for the reviewer. Never commit the completed credentials file. Do not commit actual passwords or SMTP credentials into the public repository.
- Capture screenshots from the running app for Admin dashboard, Employee dashboard, Employee management, Attendance, Leave balance/approval, Payroll, PDF salary slip, Reports, Roles & users, and document upload/download. Evidence from earlier local testing was reviewed during preparation but screenshot files, salary slips, CSV/PDF exports, SQL dumps, private documents, and local Postman environment/global files are intentionally excluded from the public Phase 3 source ZIP. Submit such artifacts separately through the approved private channel; capture only additional evidence for tests still pending.

## Validation notes and limitations

- Startup uses `Base.metadata.create_all()` for new tables plus idempotent MySQL compatibility-column additions for existing employees, attendance, and payroll tables. Back up the database before starting this version; for production, replace lightweight startup upgrades with a versioned migration tool such as Alembic.
- The salary-credit state is demonstrative only; no payment gateway or bank transfer is connected.
- Configured salary components are currently organization-wide; the data model can be extended with employee/department scopes if the next requirement calls for per-group component plans. Compensation revisions take effect based on the start date of a pay period; mid-period salary proration and statutory payroll calculations are not implemented.
- Holiday-aware summaries/leave/payroll calculations use company/department/region scope and optional holiday selections. Shift records calculate late minutes, early departure, and overtime against the assigned shift with configured grace periods; statutory/union scheduling rules are not included.
- Python syntax compilation, JSX parsing, and isolated Phase 3 endpoint workflow tests passed in the packaging environment. The frontend production build and live MySQL/API integration should still be verified on Windows before submitting. `submission/PHASE3_API_TEST_MATRIX.md` lists focused checks for the new endpoints; complete `submission/EVIDENCE_CHECKLIST.md` before final handover.
