import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { AdminPayrollPanel, EmployeePayslips } from './features/payroll/PayrollPanel'
import ReportsPanel from './features/reports/ReportsPanel'
import AttendanceAdminPanel from './features/attendance/AttendanceAdminPanel'
import AdminUsersPanel from './features/admin/AdminUsersPanel'
import DocumentsPanel from './features/documents/DocumentsPanel'
import NotificationLogPanel from './features/notifications/NotificationLogPanel'
import CalendarPanel from './features/calendar/CalendarPanel'
import ShiftManagementPanel from './features/shifts/ShiftManagementPanel'
import MyShiftPanel from './features/shifts/MyShiftPanel'
import CompensationPanel from './features/compensation/CompensationPanel'
import InAppNotificationCenter from './features/inAppNotifications/InAppNotificationCenter'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

async function api(path, { token, method = 'GET', body } = {}) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  const data = response.status === 204 ? null : await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`)
  return data
}

function Icon({ children }) { return <span className="icon" aria-hidden="true">{children}</span> }

function Login({ onLogin }) {
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('')
    try { await onLogin(email, password) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return <main className="login-wrap"><section className="login-card">
    <div className="brand-mark">P</div><p className="eyebrow">PEOPLEDESK HRMS</p>
    <h1>Welcome back</h1><p className="muted">Sign in to access your people workspace.</p>
    <form onSubmit={submit} className="form-stack">
      <label>Email address<input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" /></label>
      <label>Password<input type="password" autoComplete="current-password" required minLength="8" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" /></label>
      {error && <div className="alert error">{error}</div>}
      <button className="primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <span>→</span></button>
    </form>
    <div className="login-foot">Secure access · Role-based permissions</div>
  </section><aside className="login-aside"><div className="aside-orb orb-one"/><div className="aside-orb orb-two"/><div className="aside-content"><p className="eyebrow light">YOUR WORKPLACE, IN ONE PLACE</p><h2>People first.<br/>Work flows better.</h2><p>One place to manage employee records, daily attendance, leave requests and people operations.</p><div className="aside-points"><span>✓ Employee management</span><span>✓ Attendance and leave</span><span>✓ Protected workspaces</span></div></div></aside></main>
}

function Stat({ label, value, icon, note }) { return <article className="stat-card"><div className="stat-top"><span>{label}</span><span className="stat-icon">{icon}</span></div><strong>{value ?? '—'}</strong><small>{note}</small></article> }
function Header({ user, onLogout }) { return <header className="topbar"><div className="brand"><div className="brand-mark small">P</div><div><strong>PeopleDesk</strong><small>HR management</small></div></div><div className="top-actions"><span className="online-dot"/> <span className="role-pill">{user.role}</span><div className="avatar">{user.full_name?.split(/\s+/).map(s => s[0]).join('').slice(0,2).toUpperCase()}</div><div className="user-label"><strong>{user.full_name}</strong><small>{user.email}</small></div><button className="quiet-btn" onClick={onLogout}>Sign out</button></div></header> }

function AdminPanel({ token, notify, user }) {
  const isAdmin = user?.role === 'admin'
  const [summary, setSummary] = useState(null)
  const [employees, setEmployees] = useState([])
  const [leaves, setLeaves] = useState([])
  const [view, setView] = useState('overview')
  const [auditLogs, setAuditLogs] = useState([])
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditAction, setAuditAction] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingEmployee, setEditingEmployee] = useState(null)
  const [form, setForm] = useState({ full_name:'', email:'', password:'', employee_code:'', department:'Engineering', designation:'Software Engineer', phone:'', joining_date:new Date().toISOString().slice(0,10), monthly_salary:'60000', region:'' })
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, e, l] = await Promise.all([
        api('/dashboard/admin', { token }), api(`/employees?limit=100${search ? `&search=${encodeURIComponent(search)}` : ''}`, { token }), api('/leaves?limit=100', { token }),
      ])
      setSummary(s); setEmployees(e); setLeaves(l)
    } catch (err) { notify(err.message, 'error') } finally { setLoading(false) }
  }, [token, search, notify])
  useEffect(() => { load() }, [load])

  async function createEmployee(event) {
    event.preventDefault()
    try {
      await api('/employees', { token, method:'POST', body: { ...form, phone: form.phone || null, monthly_salary: Number(form.monthly_salary || 0) } })
      notify('Employee account created successfully.', 'success'); setShowForm(false)
      setForm({ full_name:'', email:'', password:'', employee_code:'', department:'Engineering', designation:'Software Engineer', phone:'', joining_date:new Date().toISOString().slice(0,10), monthly_salary:'60000', region:'' })
      await load()
    } catch (err) { notify(err.message, 'error') }
  }
  async function saveEmployeeUpdate(event) {
    event.preventDefault()
    if (!editingEmployee) return
    try {
      const payload = { ...editingEmployee, monthly_salary: Number(editingEmployee.monthly_salary || 0) }
      delete payload.id; delete payload.user_id; delete payload.employee_code; delete payload.created_at
      await api(`/employees/${editingEmployee.id}`, { token, method:'PATCH', body:payload })
      notify('Employee details updated.', 'success'); setEditingEmployee(null); await load()
    } catch (err) { notify(err.message, 'error') }
  }
  async function deactivateEmployee(row) {
    if (!window.confirm(`Deactivate ${row.full_name}? They will no longer be able to sign in.`)) return
    try { await api(`/employees/${row.id}`, { token, method:'DELETE' }); notify('Employee deactivated.', 'success'); await load() }
    catch (err) { notify(err.message, 'error') }
  }

  async function decideLeave(id, decision) {
    try { await api(`/leaves/${id}/decision`, { token, method:'PATCH', body:{ decision } }); notify(`Leave ${decision}.`, 'success'); await load() }
    catch (err) { notify(err.message, 'error') }
  }
  async function loadAuditLogs() {
    setAuditLoading(true)
    try {
      const suffix = auditAction ? `?limit=200&action=${encodeURIComponent(auditAction)}` : '?limit=200'
      const rows = await api(`/audit-logs${suffix}`, { token })
      setAuditLogs(Array.isArray(rows) ? rows : [])
    } catch (err) { notify(err.message, 'error') }
    finally { setAuditLoading(false) }
  }
  useEffect(() => { if (view === 'audit' && (user?.role === 'admin' || user?.role === 'hr')) loadAuditLogs() }, [view, auditAction, token, user?.role])
  const pendingCount = leaves.filter(l => l.status === 'pending').length
  return <>
    <div className="welcome-row"><div><p className="eyebrow">ADMIN WORKSPACE</p><h1>Good to see you, {summary ? 'Admin' : 'there'} <span>✦</span></h1><p className="muted">Here’s your people operations overview for today.</p></div><div className="date-chip"><Icon>◷</Icon>{new Date().toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric',year:'numeric'})}</div></div>
    <nav className="tabs"><button className={view==='overview'?'active':''} onClick={()=>setView('overview')}>Overview</button><button className={view==='employees'?'active':''} onClick={()=>setView('employees')}>Employees <span>{employees.length}</span></button><button className={view==='attendance'?'active':''} onClick={()=>setView('attendance')}>Attendance</button><button className={view==='leaves'?'active':''} onClick={()=>setView('leaves')}>Leave requests {pendingCount>0 && <i>{pendingCount}</i>}</button><button className={view==='calendar'?'active':''} onClick={()=>setView('calendar')}>Calendar</button><button className={view==='shifts'?'active':''} onClick={()=>setView('shifts')}>Shifts</button><button className={view==='payroll'?'active':''} onClick={()=>setView('payroll')}>Payroll</button><button className={view==='compensation'?'active':''} onClick={()=>setView('compensation')}>Compensation</button><button className={view==='reports'?'active':''} onClick={()=>setView('reports')}>Reports</button><button className={view==='documents'?'active':''} onClick={()=>setView('documents')}>Documents</button>{isAdmin && <button className={view==='users'?'active':''} onClick={()=>setView('users')}>Roles &amp; users</button>}{(user?.role==='admin'||user?.role==='hr') && <><button className={view==='inbox'?'active':''} onClick={()=>setView('inbox')}>In-app inbox</button><button className={view==='notifications'?'active':''} onClick={()=>setView('notifications')}>Email log</button><button className={view==='audit'?'active':''} onClick={()=>setView('audit')}>Audit logs</button></>}</nav>
    {view==='overview' && <><div className="stat-grid"><Stat label="Total employees" value={summary?.employee_count} icon="♙" note={`${summary?.active_employee_count ?? 0} active employees`}/><Stat label="Checked in today" value={summary?.checked_in_today} icon="◷" note="Attendance recorded today"/><Stat label="Pending leave" value={summary?.pending_leave_requests} icon="▤" note="Awaiting your review"/><Stat label="Payroll" value="Ready" icon="₹" note="Salary processing and PDF slips"/></div><div className="content-grid"><section className="panel"><div className="panel-head"><div><h2>Recent employees</h2><p>Latest employee records</p></div><button className="text-btn" onClick={()=>setView('employees')}>View all →</button></div><EmployeeTable rows={employees.slice(0,5)} /></section><section className="panel side-panel"><div className="panel-head"><div><h2>Needs attention</h2><p>Items waiting for you</p></div><span className="panel-icon">⌁</span></div><div className="attention-row"><div className="attention-icon amber">▤</div><div><strong>{pendingCount} leave requests</strong><p>Review pending applications</p></div><button onClick={()=>setView('leaves')} aria-label="View leave requests">→</button></div><div className="attention-row"><div className="attention-icon blue">♙</div><div><strong>Employee directory</strong><p>{employees.length} records available</p></div><button onClick={()=>setView('employees')} aria-label="View employees">→</button></div><div className="note-box">{summary?.payroll_status || 'Payroll processing is available.'} <button className="text-btn" onClick={()=>setView('payroll')}>Open payroll →</button></div></section></div></>}
    {view==='employees' && <section className="panel"><div className="panel-head"><div><h2>Employee directory</h2><p>Manage team accounts and employment details.</p></div><button className="primary" onClick={()=>setShowForm(v=>!v)}>{showForm?'Cancel':'+ Add employee'}</button></div>{showForm && <form className="employee-form" onSubmit={createEmployee}><h3>New employee</h3><div className="form-grid"><label>Full name<input required minLength="2" value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></label><label>Email<input required type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Temporary password<input required minLength="8" type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><label>Employee code<input required value={form.employee_code} onChange={e=>setForm({...form,employee_code:e.target.value})} placeholder="EMP001"/></label><label>Department<select value={form.department} onChange={e=>setForm({...form,department:e.target.value})}><option>Engineering</option><option>Human Resources</option><option>Finance</option><option>Operations</option><option>Sales</option><option>Marketing</option></select></label><label>Designation<input required value={form.designation} onChange={e=>setForm({...form,designation:e.target.value})}/></label><label>Phone<input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label><label>Region (for regional holidays)<input value={form.region||''} onChange={e=>setForm({...form,region:e.target.value})} placeholder="e.g. Bihar"/></label><label>Joining date<input type="date" required value={form.joining_date} onChange={e=>setForm({...form,joining_date:e.target.value})}/></label><label>Monthly salary (₹)<input type="number" min="0" step="0.01" required value={form.monthly_salary} onChange={e=>setForm({...form,monthly_salary:e.target.value})}/></label></div><button className="primary" type="submit">Create employee account</button></form>}<div className="table-tools"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search name, email or employee code…"/><span>{employees.length} employees</span></div>{editingEmployee && <form className="employee-form" onSubmit={saveEmployeeUpdate}><h3>Edit employee · {editingEmployee.employee_code}</h3><div className="form-grid"><label>Full name<input required minLength="2" value={editingEmployee.full_name} onChange={e=>setEditingEmployee({...editingEmployee,full_name:e.target.value})}/></label><label>Email<input required type="email" value={editingEmployee.email} onChange={e=>setEditingEmployee({...editingEmployee,email:e.target.value})}/></label><label>Department<input required value={editingEmployee.department} onChange={e=>setEditingEmployee({...editingEmployee,department:e.target.value})}/></label><label>Designation<input required value={editingEmployee.designation} onChange={e=>setEditingEmployee({...editingEmployee,designation:e.target.value})}/></label><label>Phone<input value={editingEmployee.phone||''} onChange={e=>setEditingEmployee({...editingEmployee,phone:e.target.value})}/></label><label>Region<input value={editingEmployee.region||''} onChange={e=>setEditingEmployee({...editingEmployee,region:e.target.value})} placeholder="e.g. Bihar"/></label><label>Joining date<input type="date" required value={editingEmployee.joining_date} onChange={e=>setEditingEmployee({...editingEmployee,joining_date:e.target.value})}/></label><label>Monthly salary (₹)<input required type="number" min="0" step="0.01" value={editingEmployee.monthly_salary} onChange={e=>setEditingEmployee({...editingEmployee,monthly_salary:e.target.value})}/></label><label>Employment status<select value={editingEmployee.employment_status} onChange={e=>setEditingEmployee({...editingEmployee,employment_status:e.target.value})}><option value="active">Active</option><option value="inactive">Inactive</option></select></label></div><div className="button-row"><button className="primary" type="submit">Save changes</button><button className="secondary" type="button" onClick={()=>setEditingEmployee(null)}>Cancel</button></div></form>}<EmployeeTable rows={employees} onEdit={setEditingEmployee} onDeactivate={deactivateEmployee}/></section>}
    {view==='leaves' && <section className="panel"><div className="panel-head"><div><h2>Leave requests</h2><p>Review and respond to employee applications.</p></div><span className="status pending">{pendingCount} pending</span></div><LeaveTable rows={leaves} onDecision={decideLeave}/></section>}
    {view==='calendar' && <CalendarPanel token={token} notify={notify} isAdmin={true}/>}
    {view==='shifts' && <ShiftManagementPanel token={token} notify={notify} employees={employees}/>}
    {view==='compensation' && <CompensationPanel token={token} notify={notify} employees={employees}/>}
    {view==='inbox' && <InAppNotificationCenter token={token} notify={notify} user={user} employees={employees}/>}
    {view==='payroll' && <AdminPayrollPanel token={token} notify={notify} employees={employees}/>}
    {view==='attendance' && <AttendanceAdminPanel token={token} notify={notify} employees={employees}/>}
    {view==='reports' && <ReportsPanel token={token} notify={notify} employees={employees}/>}
    {view==='documents' && <DocumentsPanel token={token} notify={notify} employees={employees} user={user}/>}
    {view==='users' && isAdmin && <AdminUsersPanel token={token} notify={notify} currentUser={user}/>}
    {view==='notifications' && (user?.role==='admin'||user?.role==='hr') && <NotificationLogPanel token={token} notify={notify}/>}
    {view==='audit' && (user?.role==='admin'||user?.role==='hr') && <section className="panel"><div className="panel-head"><div><h2>Audit logs</h2><p>Read-only history of administrative and employee actions.</p></div><button className="secondary" onClick={loadAuditLogs} disabled={auditLoading}>{auditLoading?'Refreshing…':'Refresh logs'}</button></div><div className="table-tools"><select value={auditAction} onChange={e=>setAuditAction(e.target.value)} aria-label="Filter audit action"><option value="">All actions</option>{[...new Set(auditLogs.map(row=>row.action))].sort().map(action=><option key={action} value={action}>{action}</option>)}</select><span>{auditLogs.length} records loaded · newest first</span></div>{auditLoading?<div className="loading-line">Loading audit history…</div>:<div className="table-wrap"><table><thead><tr><th>Timestamp</th><th>Action</th><th>Entity</th><th>Entity ID</th><th>Actor user ID</th><th>Details</th></tr></thead><tbody>{auditLogs.map(row=><tr key={row.id}><td className="mono">{row.created_at?new Date(row.created_at).toLocaleString(): '—'}</td><td><span className="status approved">{row.action}</span></td><td>{row.entity_type||'—'}</td><td>{row.entity_id??'—'}</td><td>{row.actor_user_id??'System'}</td><td className="reason-cell">{row.details?JSON.stringify(row.details):'—'}</td></tr>)}{auditLogs.length===0&&<tr><td colSpan="6" className="empty">No audit events found for this filter.</td></tr>}</tbody></table></div>}<p className="muted">Audit entries are read-only. This screen does not expose edit or delete actions.</p></section>}
    {loading && <div className="loading-line">Refreshing dashboard…</div>}
  </>
}

function EmployeeTable({ rows, onEdit, onDeactivate }) { return <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Employee ID</th><th>Department</th><th>Designation</th><th>Monthly salary</th><th>Status</th>{onEdit && <th>Actions</th>}</tr></thead><tbody>{rows.map(r=><tr key={r.id}><td><div className="person-cell"><div className="table-avatar">{r.full_name?.charAt(0)?.toUpperCase()||'E'}</div><div><strong>{r.full_name}</strong><small>{r.email}</small></div></div></td><td className="mono">{r.employee_code}</td><td>{r.department}</td><td>{r.designation}</td><td>₹{Number(r.monthly_salary||0).toLocaleString('en-IN',{maximumFractionDigits:2})}</td><td><span className={`status ${r.employment_status==='active'?'approved':'rejected'}`}>{r.employment_status}</span></td>{onEdit && <td><div className="action-pair"><button className="secondary small-btn" onClick={()=>onEdit({...r,monthly_salary:String(r.monthly_salary??0)})}>Edit</button>{r.employment_status==='active' && onDeactivate && <button className="reject-btn" onClick={()=>onDeactivate(r)}>Deactivate</button>}</div></td>}</tr>)}{rows.length===0&&<tr><td colSpan={onEdit?7:6} className="empty">No employees found yet.</td></tr>}</tbody></table></div> }
function LeaveTable({ rows, onDecision }) { return <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Leave type</th><th>Dates</th><th>Reason</th><th>Status / action</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td><strong>{r.employee_name||`Employee #${r.employee_id}`}</strong><small className="block">{r.employee_code||''}</small></td><td>{r.leave_type}</td><td>{r.start_date}<small className="block">to {r.end_date}</small></td><td className="reason-cell">{r.reason}</td><td>{r.status==='pending'?<div className="action-pair"><button className="approve-btn" onClick={()=>onDecision(r.id,'approved')}>Approve</button><button className="reject-btn" onClick={()=>onDecision(r.id,'rejected')}>Reject</button></div>:<span className={`status ${r.status}`}>{r.status}</span>}</td></tr>)}{rows.length===0&&<tr><td colSpan="5" className="empty">No leave applications yet.</td></tr>}</tbody></table></div> }

function EmployeePanel({ token, user, notify }) {
  const [dashboard, setDashboard] = useState(null)
  const [attendance, setAttendance] = useState([])
  const [leaves, setLeaves] = useState([])
  const [leaveBalances, setLeaveBalances] = useState([])
  const [leaveForm, setLeaveForm] = useState({ start_date:new Date().toISOString().slice(0,10), end_date:new Date().toISOString().slice(0,10), leave_type:'annual', reason:'' })
  const [busy, setBusy] = useState(false)
  const load = useCallback(async()=>{try{const [d,a,l,b]=await Promise.all([api('/dashboard/employee',{token}),api('/attendance/me?limit=14',{token}),api('/leaves/me',{token}),api('/leaves/balance/me',{token})]);setDashboard(d);setAttendance(a);setLeaves(l);setLeaveBalances(b)}catch(err){notify(err.message,'error')}},[token,notify])
  useEffect(()=>{load()},[load])
  async function attendanceAction(action){setBusy(true);try{await api(`/attendance/${action}`,{token,method:'POST'});notify(action==='check-in'?'Checked in successfully.':'Checked out successfully.','success');await load()}catch(err){notify(err.message,'error')}finally{setBusy(false)}}
  async function applyLeave(event){event.preventDefault();setBusy(true);try{await api('/leaves',{token,method:'POST',body:leaveForm});notify('Leave application submitted.','success');setLeaveForm({...leaveForm,reason:''});await load()}catch(err){notify(err.message,'error')}finally{setBusy(false)}}
  const today = dashboard?.attendance_today
  return <><div className="welcome-row"><div><p className="eyebrow">EMPLOYEE WORKSPACE</p><h1>Hello, {user.full_name.split(' ')[0]} <span>✦</span></h1><p className="muted">Here’s your attendance and leave overview.</p></div><div className="date-chip">◷ {new Date().toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'})}</div></div><div className="stat-grid"><Stat label="Employee ID" value={dashboard?.employee_code||'—'} icon="♙" note={dashboard?.department||'Loading profile'}/><Stat label="Today's attendance" value={today?.check_in?(today?.check_out?'Completed':'Checked in'):'Not checked in'} icon="◷" note={today?.check_in?`In ${new Date(today.check_in+'Z').toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`:'Remember to check in'}/><Stat label="Pending leave" value={dashboard?.pending_leave_requests??0} icon="▤" note="Awaiting manager review"/><Stat label="Monthly salary" value={dashboard?.monthly_salary != null ? `₹${Number(dashboard.monthly_salary).toLocaleString('en-IN',{maximumFractionDigits:2})}` : '—'} icon="₹" note="Base salary on your profile"/></div><div className="content-grid"><section className="panel"><div className="panel-head"><div><h2>Today's attendance</h2><p>Record your workday in two clicks.</p></div><span className={`status ${today?.check_out?'approved':today?.check_in?'pending':'neutral'}`}>{today?.check_out?'Completed':today?.check_in?'In progress':'Not started'}</span></div><div className="attendance-actions"><div className="time-card"><span>Check-in</span><strong>{today?.check_in?new Date(today.check_in+'Z').toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'—:—'}</strong></div><div className="time-divider">→</div><div className="time-card"><span>Check-out</span><strong>{today?.check_out?new Date(today.check_out+'Z').toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'—:—'}</strong></div></div><div className="button-row"><button className="primary" disabled={busy||Boolean(today?.check_in)} onClick={()=>attendanceAction('check-in')}>Check in</button><button className="secondary" disabled={busy||!today?.check_in||Boolean(today?.check_out)} onClick={()=>attendanceAction('check-out')}>Check out</button></div><div className="subsection"><div className="panel-head"><div><h2>Attendance history</h2><p>Your recent recorded workdays.</p></div></div><div className="history-list">{attendance.slice(0,7).map(a=><div className="history-row" key={a.id}><div><strong>{new Date(a.work_date+'T00:00:00').toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'})}</strong><small>{a.check_in?'Checked in':'No check-in'}{a.check_out?' · Checked out':''}</small></div><span className={`status ${a.check_out?'approved':'pending'}`}>{a.check_out?'Complete':'Open'}</span></div>)}{attendance.length===0&&<p className="empty">Your attendance records will appear here.</p>}</div></div></section><section className="panel"><div className="panel-head"><div><h2>Apply for leave</h2><p>Submit an application for manager review.</p></div><span className="panel-icon">▤</span></div><form className="form-stack leave-form" onSubmit={applyLeave}><label>Leave type<select value={leaveForm.leave_type} onChange={e=>setLeaveForm({...leaveForm,leave_type:e.target.value})}><option value="annual">Annual leave</option><option value="sick">Sick leave</option><option value="personal">Personal leave</option><option value="unpaid">Unpaid leave</option></select></label><div className="form-grid two"><label>Start date<input type="date" required value={leaveForm.start_date} onChange={e=>setLeaveForm({...leaveForm,start_date:e.target.value})}/></label><label>End date<input type="date" required min={leaveForm.start_date} value={leaveForm.end_date} onChange={e=>setLeaveForm({...leaveForm,end_date:e.target.value})}/></label></div><label>Reason<textarea required minLength="5" maxLength="2000" rows="3" value={leaveForm.reason} onChange={e=>setLeaveForm({...leaveForm,reason:e.target.value})} placeholder="Briefly explain your request…"/></label><button className="primary full" disabled={busy}>Submit leave request</button></form><div className="subsection"><div className="panel-head"><div><h2>Leave balance</h2><p>Weekdays only; approved paid leave uses this balance.</p></div></div><div className="leave-balance-grid">{leaveBalances.map(balance=><div className="leave-balance" key={balance.leave_type}><span>{balance.leave_type}</span><strong>{balance.available_days}</strong><small>of {balance.allocated_days} days available</small></div>)}</div></div><div className="subsection"><div className="panel-head"><div><h2>Leave tracking</h2><p>Track the status of your requests.</p></div></div><div className="history-list">{leaves.slice(0,6).map(l=><div className="history-row" key={l.id}><div><strong>{l.leave_type.charAt(0).toUpperCase()+l.leave_type.slice(1)} leave</strong><small>{l.start_date} → {l.end_date}</small></div><span className={`status ${l.status}`}>{l.status}</span></div>)}{leaves.length===0&&<p className="empty">No leave requests submitted yet.</p>}</div></div></section></div><EmployeePayslips token={token} notify={notify}/><div className="section-spaced"><MyShiftPanel token={token} notify={notify}/></div><div className="section-spaced"><CalendarPanel token={token} notify={notify} compact/></div><div className="section-spaced"><InAppNotificationCenter token={token} notify={notify} user={user} compact/></div><div className="section-spaced"><DocumentsPanel token={token} notify={notify} user={user}/></div></>
}

export default function App() {
  const [session, setSession] = useState(()=>{try{return JSON.parse(localStorage.getItem('hrms_session')||'null')}catch{return null}})
  const [toast, setToast] = useState(null)
  const notify = useCallback((message,type='success')=>{setToast({message,type});window.setTimeout(()=>setToast(null),4000)},[])
  async function login(email,password){const result=await api('/auth/login',{method:'POST',body:{email,password}});const next={token:result.access_token,user:result.user};localStorage.setItem('hrms_session',JSON.stringify(next));setSession(next)}
  function logout(){localStorage.removeItem('hrms_session');setSession(null)}
  useEffect(()=>{if(!session?.token)return;api('/auth/me',{token:session.token}).then(user=>setSession(s=>s?{...s,user}:s)).catch(()=>logout())},[])
  if(!session?.token)return <><Login onLogin={login}/>{toast&&<div className={`toast ${toast.type}`}>{toast.message}</div>}</>
  return <div className="app-shell"><Header user={session.user} onLogout={logout}/><main className="dashboard-main">{['admin','hr'].includes(session.user.role)?<AdminPanel token={session.token} notify={notify} user={session.user}/>:<EmployeePanel token={session.token} user={session.user} notify={notify}/>}<footer className="app-footer"><span>PeopleDesk HRMS</span><span>People operations, simplified.</span></footer></main>{toast&&<div className={`toast ${toast.type}`}>{toast.message}</div>}</div>
}
