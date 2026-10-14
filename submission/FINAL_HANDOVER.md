# PeopleDesk HRMS — Submission Handover

## Included in this package
- React/Vite frontend and FastAPI backend source.
- MySQL schema reference at `database/hrms_schema.sql`.
- Final 44-request Postman collection, plus Day 1 and Day 2 collections.
- Report exports (attendance, leave, payroll) in CSV and PDF formats.
- Sample salary slip PDF at `submission/sample_salary_slip.pdf`.
- Screenshots provided during local testing in `submission/local_evidence/`.
- Evidence checklist, Postman test matrix, and private credentials template.

## Requires local completion
- The actual MySQL dump is intentionally excluded from this ZIP. The verified dump already exists on the developer's local machine at `database/hrms_db_dump.sql`; submit it as a separate private file or include it in the approved private submission channel. Never commit it to a public GitHub repository.
- The actual Admin/Employee passwords and GitHub URL must be entered by the owner in a private handover copy.
- Run `npm run build` from `frontend` and the backend against the local MySQL database after applying the update.
- Open Admin/HR → Notifications, verify the records and capture `09_notification_log.png`.
- Run the required Postman tests locally and update `submission/POSTMAN_TEST_MATRIX.md` with actual outcomes.
- Verify payroll locking, simulated credit, and Loss of Pay using a fresh test period before final submission.

## Security
Do not share `.env`, passwords, JWT tokens, SMTP credentials, or uploaded employee documents. Keep the SQL dump private. Rotate any credentials that were included in an earlier archive before publishing code publicly.

## Scope note
Salary credit is a simulation only. Email delivery occurs only when valid SMTP settings are configured; otherwise the system records attempts as `logged`.
