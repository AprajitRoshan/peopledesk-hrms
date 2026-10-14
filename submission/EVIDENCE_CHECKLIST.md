# PeopleDesk HRMS — Final Evidence Checklist

Use this checklist for the project handover. A checked screenshot proves the displayed page was captured; it does not automatically prove every underlying workflow has passed.

## Existing evidence in this package
- [x] `local_evidence/01_admin_dashboard.png` — Admin dashboard
- [x] `local_evidence/02_employee_dashboard.png` — Employee workspace and attendance/leave overview
- [x] `local_evidence/03_salary_slips_and_documents.png` — Employee salary-slip and document area
- [x] `local_evidence/04_admin_documents.png` — Admin document management
- [x] `local_evidence/05_reports_analytics.png` — Reports, filters and CSV/PDF export controls
- [x] `local_evidence/06_attendance_csv_opened.png` — Attendance CSV opened in Excel
- [x] `local_evidence/07_roles_and_permissions.png` — Role management UI
- [x] `local_evidence/08_audit_logs.png` — Read-only audit records
- [x] `sample_salary_slip.pdf` — Sample salary slip exported from the app
- [x] `attendance_report.csv` and `attendance_report.pdf`
- [x] `leaves_report.csv` and `leaves_report.pdf`
- [x] `payroll_report.csv` and `payroll_report.pdf`

## Still verify on the local machine
- [ ] Open the new Admin/HR Notifications tab, verify existing attempts load, then capture `09_notification_log.png`.
- [ ] Determine whether SMTP is configured. `logged` means recorded but not emailed; `sent` means SMTP accepted the message; `failed` shows delivery attempt failure.
- [ ] Process a fresh test payroll period with approved unpaid leave to verify LOP deduction; do not duplicate the already processed October payroll.
- [ ] Lock a test payroll record, confirm adjustments are rejected, then simulate credit and confirm status changes to `credited`. Explain that credit is only a simulation.
- [ ] Import `../postman/HRMS_Final.postman_collection.json`, set local variables, and run the requests that do not create duplicate/test records unintentionally.
- [ ] Save Postman test results or an exported run report if the reviewer requests API evidence.
- [ ] Run `npm run build` and `python -m compileall -q backend/app` on the Windows machine and resolve any errors.
- [ ] Check `git status --short` and verify `.env`, database dumps, uploaded documents, dependencies, JWT tokens, and passwords are not staged.
- [ ] Verify GitHub source has been pushed and copy the repository URL into the handover document.
- [ ] Fill actual Admin/Employee passwords only in a private copy of `CREDENTIALS_TEMPLATE.md`; never commit that filled copy.

## Screenshot guidance
Capture new screenshots only for outstanding items. Hide tokens, passwords and personal information. Use dummy employee information only.
