# HRMS Postman Test Matrix — 66 requests

Import `../postman/HRMS_Final.postman_collection.json` into Postman. It contains 66 requests across the existing modules and Phase 3 additions. Phase 3-specific request-by-request expected results are in `PHASE3_API_TEST_MATRIX.md`. Set `baseUrl` to `http://127.0.0.1:8000/api`. Enter passwords locally in Postman variables; never export real passwords or tokens.

## Suggested order

| Step | Request group / action | Expected result | Local result |
|---|---|---|---|
| 1 | Health · API and Health · Database connection | HTTP 200 | Pending local run |
| 2 | Admin login | HTTP 200; saves `adminToken` if the test script is enabled | Pending local run |
| 3 | Employee login | HTTP 200; saves `employeeToken` if the test script is enabled | Pending local run |
| 4 | Admin dashboard, employee profile, employee list | HTTP 200 | Pending local run |
| 5 | Employee attendance and leave history | HTTP 200; use a fresh date/request when creating records | Pending local run |
| 6 | Admin leave list / decision | HTTP 200; only approve/reject a suitable pending test request | Pending local run |
| 7 | Payroll list, salary slip, notifications | HTTP 200; avoid processing a duplicate employee/pay-period | Pending local run |
| 8 | Lock and credit simulation | Lock a suitable processed test record first; credit is simulation-only | Pending local run |
| 9 | Document listing / download | HTTP 200; set `documentId` to an ID returned by the list endpoint | Pending local run |
| 10 | Reports CSV/PDF endpoints | HTTP 200 and file response | Pending local run |
| 11 | Employee access to Admin user management | HTTP 403 | Pending local run |
| 12 | Admin read-only audit logs | HTTP 200 | Pending local run |

## Important notes
- The collection includes state-changing requests. Read each request description before using **Run collection**; requests like create employee, apply leave, process payroll, lock payroll, and credit simulation alter test data.
- For “Employees · Create sample employee,” use a unique email and employee code if the sample values already exist.
- The annual leave balance route must be `/leaves/balance/{{employeeId}}/annual`.
- The document upload request requires selecting a real dummy PDF/PNG/JPEG file in Postman form-data with key `file`.
- Mark local result values only after seeing the actual responses; this document intentionally does not claim unrun tests passed.
