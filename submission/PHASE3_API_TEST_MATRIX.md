# Phase 3 API Verification Matrix — PeopleDesk HRMS

Use this matrix after updating the local source, restarting FastAPI, and keeping the React frontend running. Authenticate with the existing Admin/HR or Employee account. Do not run this as a single bulk collection against records that should be preserved.

Base URL: `http://127.0.0.1:8000/api`

## Holiday & calendar management

| Request | Expected outcome | Caution |
|---|---|---|
| `GET /holidays?month=2026-11` | Active holidays visible to the current employee or manager | Read-only |
| `GET /holidays?year=2026` | Year calendar data | Read-only |
| `POST /holidays` with `holiday_type=company` | `201`; holiday appears in month/year views | Use a unique test holiday name/date |
| `POST /holidays` with `holiday_type=regional` and `region` or `department` | `201`; scope is reflected in employee filtering | Regional holiday must have a region or department |
| `POST /holidays/{id}/select` as employee for an optional holiday | Selection is recorded and employee holiday logic includes it | Optional holidays only |
| `DELETE /holidays/{id}` as Admin/HR | Holiday is deactivated; history retained | Does not hard-delete the row |
| `GET /attendance/summary/me?month=YYYY-MM` | `expected_workdays` and holiday list exclude applicable holidays | Compare with configured calendar |

## In-app notification center

| Request | Expected outcome | Caution |
|---|---|---|
| `GET /in-app-notifications/me` | Only current user's notifications; includes unread count | Read-only |
| `PATCH /in-app-notifications/{notification_id}/read` | Own notification becomes read | Using another user's ID should return `404` |
| `POST /in-app-notifications/read-all` | Current user's notifications are marked read | Changes read state for current user only |
| `GET /in-app-notifications/preferences/me` | Current user's category preferences | Read-only apart from initial preference-row creation |
| `PATCH /in-app-notifications/preferences/me` | Preference saved | Test a reversible change |
| `POST /in-app-notifications/broadcast` as Admin/HR | Creates user-specific notices for organization or chosen department; preferences respected | Use a clear `[TEST]` title and do not send sensitive data |

## Shift & work schedule

| Request | Expected outcome | Caution |
|---|---|---|
| `GET /shifts` | Active shift definitions | Read-only |
| `POST /shifts` | `201`; definition saved | Use unique shift name, e.g. `QA General 09-18` |
| `POST /shifts/assignments` for one employee or department | `201`; effective-dated assignment saved and prior active assignment retained as history | Confirm target and effective date before submitting |
| `GET /shifts/me/current` as Employee | Employee-specific shift or department shift, if assigned | Read-only |
| `GET /shifts/attendance-report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | Shift-wise attendance rows including late, early and overtime minutes | Read-only |
| `POST /attendance/override` | Updated attendance metrics and audit record | Only use a test date/record and include a correction note |

## Advanced payroll & compensation

| Request | Expected outcome | Caution |
|---|---|---|
| `GET /compensation/components` | Configured salary component list | Read-only |
| `POST /compensation/components` | `201`; fixed or percent-of-basic component is saved | Use a unique component code/name; check payroll impact before activating |
| `GET /compensation/revisions?employee_id={id}` | Effective-dated historical pay revisions | Read-only |
| `POST /compensation/revisions` | `201`; revision created and prior open-ended revision closed to the preceding day | Use future or approved effective date; cannot reuse an effective date |
| `POST /payroll` with bonus/variable pay | Creates payroll with configured earnings/deductions, overtime and LOP breakdown | Duplicate employee-period is blocked; use an unused employee-period only |
| `POST /payroll/{id}/lock` and `/credit` | Transitions processed → locked → credited | Credit is simulation only; do not repeat on existing payroll |
| `GET /payroll/{id}/salary-slip.pdf` | PDF includes basic, allowances, bonus, variable, overtime, components and deductions | Employees can only fetch their own slip unless Admin/HR |

## Safety / access checks

- Employee requests against Admin/HR-only shift, compensation, holiday write, and broadcast endpoints should be denied.
- Employee cannot read another user's in-app notification (`404` on a notification ID not owned by them).
- Never include `.env`, database dumps, real employee documents, passwords, JWT tokens, SMTP secrets, or local Postman environment/global values in a public Git repository.
- Existing endpoints have been syntax-checked here but the updated modules still require live integration testing against the user's local MySQL database.
