# Private Reviewer Handover Template

**Important:** This is a template. Do not write real passwords in this file while it is inside a source repository. Copy it to a private location such as `CREDENTIALS_PRIVATE.md`, fill it there, and share it only through the approved submission channel.

## Project
- Project: PeopleDesk HRMS
- Stack: React + Vite, FastAPI, SQLAlchemy, MySQL, JWT
- GitHub repository URL: `FILL_IN_AFTER_PUSH`
- UI URL / deployment URL (if applicable): `LOCAL_ONLY_OR_DEPLOYMENT_URL`

## Sample accounts
- Admin email: `admin@example.com`
- Admin password: `ENTER_PRIVATELY`
- Employee email: `rahul.employee@example.com`
- Employee password: `ENTER_PRIVATELY`

## Deliverables
- Database schema: `database/hrms_schema.sql`
- Actual local database dump: generated separately at `database/hrms_db_dump.sql`; keep private and do not commit publicly.
- Postman collection: `postman/HRMS_Final.postman_collection.json`
- Sample salary slip: `submission/sample_salary_slip.pdf`
- Screenshots and report exports: `submission/local_evidence/` and `submission/`

## Notes for reviewer
- Salary credit is simulated only; no bank transfer or payment gateway is connected.
- Email delivery depends on SMTP configuration. A `logged` notification indicates the attempt was stored in the notification log, not that the email was delivered.
- Replace these notes with any locally verified limitations and test outcomes before submitting.
