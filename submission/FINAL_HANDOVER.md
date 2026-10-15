# PeopleDesk HRMS — Phase 3 Handover

## Phase 3 scope added
- Holiday and calendar management: company, regional, and optional holidays; monthly/yearly views; optional selections; holiday-aware workday calculations.
- In-app notification center: user-specific feed, unread/read tracking, read-all, preference toggles, Admin/HR department or organization broadcasts. Existing email notification logs remain separate.
- Shift and work schedule management: general/night/flexible/remote shift definitions, effective-dated employee or department assignment history, late/early/overtime metrics, shift attendance report.
- Advanced compensation: salary component catalogue, effective-dated compensation revisions, bonus and variable pay, configured components, overtime, detailed payslip breakdown, and holiday-aware LOP.

## Source and test files
- `backend/`: FastAPI endpoints and SQLAlchemy models.
- `frontend/`: React/Vite modules and UI for calendar, inbox, shifts, compensation, and expanded payroll.
- `database/hrms_schema.sql`: fresh-install schema reference.
- `database/README.md`: database notes.
- `postman/HRMS_Final.postman_collection.json`: consolidated 66-request collection, including Phase 3 endpoints. The user’s Postman Local Mode workspace may have converted collections to v3 YAML; the JSON is kept as a portable submission definition.
- `submission/PHASE3_IMPLEMENTATION_NOTES.md`, `PHASE3_API_TEST_MATRIX.md`, `POSTMAN_TEST_MATRIX.md`, and `EVIDENCE_CHECKLIST.md`: implementation, API verification, and handover guidance.

## Validation status
- Python syntax compilation: passed in the packaging environment.
- Backend app import and route registration: checked with an isolated test setup.
- Phase 3 route workflow tests: passed against a temporary isolated SQLite database in the packaging environment (holiday scope, optional selections, notification feed/preferences/broadcast, shift assignment/history, salary component/revision, holiday-aware leave/LOP and bonus processing). This is not the user's production/local MySQL database.
- Frontend JSX parse: passed. The packaging environment could not run the Windows frontend's native Rolldown dependency; after applying this update on Windows, run `npm install` then `npm run build` to verify the local production build.
- Live MySQL integration for the new schema and screens remains to be verified on the target machine.

## Apply update to the existing Windows project
1. Make a fresh database backup first.
2. Stop FastAPI and Vite.
3. Extract the source ZIP to a temporary directory. Copy/merge the new `backend`, `frontend`, `database`, `postman`, `README.md`, and `submission` source/document files into `D:\Stackly_training\hrms`. Keep local `.env`, the existing `database\hrms_db_dump.sql`, `backend\storage`, `backend\venv`, `frontend\node_modules`, and private evidence/credentials folders. Do not overwrite the local database or secrets.
4. In `backend`, install dependencies if needed and restart FastAPI. Startup creates new tables and adds compatibility columns for existing tables; back up first.
5. In `frontend`, run `npm install` and `npm run build`, then `npm run dev` for the UI. Verify the four Phase 3 tabs and core flows using `submission/PHASE3_API_TEST_MATRIX.md`.
6. Review the updated Postman request data before running write operations. Do not run the entire collection against existing live test data.
7. Only after local verification, commit and push the changed source to `https://github.com/AprajitRoshan/peopledesk-hrms`. The previously published GitHub commit does not automatically include this Phase 3 update until it is pushed.

## Security and operational limitations
- `.env`, passwords, JWT tokens, SMTP credentials, local Postman environment/global variables, SQL dumps, PDFs/CSVs, screenshots, and stored employee documents are intentionally excluded from the Phase 3 source ZIP. Provide private deliverables through the approved submission channel.
- Salary credit is a simulation; no real payment gateway or bank transfer is connected.
- Attendance/LOP uses a weekday-based demonstration model. This is not legal/tax advice and does not implement jurisdiction-specific PF/ESI/income-tax rules.
- For production, replace lightweight startup compatibility alters with a versioned migration tool such as Alembic and review schema changes in staging first.
