# Phase 3 — Implementation Notes

This update adds four modules to the existing PeopleDesk HRMS without replacing the project scaffold.

## 1. Holiday & Calendar Management
- Admin/HR create, update, and deactivate company-wide, regional, and optional holidays.
- Employees can view monthly and yearly calendars, including applicable department/region holidays.
- Employees can select optional holidays; working-day calculations for leave balances, attendance expectations, and LOP ignore applicable non-working holidays.
- `Employee.region` is now supported so regional scope can be matched.

## 2. In-app Notification Center
- Notifications are user-scoped; employees cannot query another user's records.
- Read/unread and read-all actions plus category preferences are available.
- Admin/HR can broadcast to the organization or a department, with recipient notification preferences respected.
- Leave actions, payroll processing/credit, and shift-based attendance alerts create in-app entries. Existing email notification logging stays separate.

## 3. Shift & Work Schedule
- Defines general, night, flexible, and remote shift templates with start/end, grace, break and overtime threshold settings.
- Effective-dated employee or department assignments preserve old assignment records as history.
- Check-in/check-out and Admin override compute late, early checkout, and overtime minutes. Shift-wise attendance report supports date, department, and shift filters.

## 4. Advanced Payroll & Compensation
- Salary component catalogue supports fixed or percent-of-basic earnings and deductions.
- Employee compensation revisions are date-effective and historical; the existing pay period picks the revision active on the month's first day when the form leaves base salary blank.
- Payroll computes base + allowances + bonus + variable pay + configured earnings + overtime + adjustment − other deductions − configured deductions − LOP.
- Salary slips show the detailed earnings and deduction breakdown. Payroll lock/credit states remain as before; credit is simulation-only.

## Database behavior
- New tables are created by SQLAlchemy `Base.metadata.create_all()` on startup.
- `ensure_compatibility_columns()` adds phase-3 columns to existing `employees`, `attendance`, and `payroll_records` without dropping data.
- A current complete schema reference is in `database/hrms_schema.sql`.
- Back up `hrms_db` before starting updated code. For production, replace startup ALTERs with versioned Alembic migrations.

## Validation performed in the packaging environment
- Python syntax compilation (`compileall`) passed.
- A frontend bundle build could not be executed in this Linux packaging environment because the uploaded `node_modules` folder lacks a Linux Rolldown native optional binding. On Windows, install dependencies with `npm install` in `frontend/` and run `npm run build`.
- This is not a live MySQL integration test. Verify the new endpoints/screens locally and use `submission/PHASE3_API_TEST_MATRIX.md`.
