# PeopleDesk HRMS — Evidence Checklist

Use this checklist for the final handover. Some UI evidence and export files were provided/verified in the previous local project, but are intentionally excluded from the public Phase 3 source package because they can contain employee, salary, or environment-specific information. Attach them separately through the authorized private submission channel if the reviewer requires them.

## Previously verified on the local Phase 2 app (keep private / submit separately)
- [x] Admin dashboard screenshot
- [x] Employee dashboard screenshot
- [x] Salary slips and employee document panel
- [x] Admin employee document management; dummy PDF uploaded and downloadable
- [x] Reports & Analytics screen; date/department filters and CSV/PDF export controls
- [x] Attendance CSV opened in Excel
- [x] Roles & Users screen covering Admin, HR and Employee role options
- [x] Audit log screen showing timestamped employee, attendance, leave, payroll and document actions
- [x] Notification log screen; one new leave notification showed `Sent`, and corresponding email arrived in Gmail
- [x] Payroll LOP calculation on November test record: 2 LOP days, ₹4,285.71 deduction, ₹40,714.29 net salary
- [x] Payroll lock and simulated credit verified; credit is not a bank transfer
- [x] API health and database health returned `200 OK`; Admin login returned `200 OK` before credential rotation
- [x] Previous phase report exports and sample salary slip PDF were produced locally; do not commit salary slips or report files publicly

## Phase 3 verification still required on Windows + local MySQL
- [ ] Holiday monthly/yearly view; create/deactivate a company or regional holiday; select an optional holiday as employee
- [ ] Confirm attendance expected-workday/monthly summary excludes applicable holidays
- [ ] In-app notification feed, unread/read/read-all, preferences, and Admin/HR announcement broadcast
- [ ] Define and assign a work shift; confirm history and shift-wise attendance report; verify late/early/overtime metrics on a safe test date
- [ ] Create a salary component and a future-dated compensation revision; verify history and component calculations
- [ ] Process a fresh test payroll with bonus/variable pay only for a new employee-period combination and check the detailed PDF breakdown
- [ ] On Windows, run `npm install` then `npm run build` in `frontend` and `python -m compileall -q app` in `backend`
- [ ] Keep database dump, credentials note, real salary slips, report exports, screenshots, employee documents and SMTP secrets out of public GitHub
- [ ] After local verification, commit and push the Phase 3 changes; confirm the repository shows the intended latest commit

## Screenshot guidance
Capture new screenshots only for outstanding Phase 3 flows. Hide passwords, tokens, personal email addresses, and private salary details where they are not necessary to prove the feature. Use dummy employee data when possible.
