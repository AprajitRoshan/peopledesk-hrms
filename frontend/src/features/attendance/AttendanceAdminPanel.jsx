import { useCallback, useEffect, useMemo, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
const today = new Date().toISOString().slice(0, 10)
const month = today.slice(0, 7)

function localDateTime(value) {
  if (!value) return ''
  return String(value).replace(' ', 'T').slice(0, 16)
}

export default function AttendanceAdminPanel({ token, notify, employees = [] }) {
  const [startDate, setStartDate] = useState(`${month}-01`)
  const [endDate, setEndDate] = useState(today)
  const [monthFilter, setMonthFilter] = useState(month)
  const [department, setDepartment] = useState('')
  const [rows, setRows] = useState([])
  const [summary, setSummary] = useState([])
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(false)

  const departments = useMemo(() => [...new Set(employees.map(row => row.department).filter(Boolean))].sort(), [employees])
  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ start_date: startDate, end_date: endDate })
      if (department) params.set('department', department)
      const summaryParams = new URLSearchParams({ month: monthFilter })
      if (department) summaryParams.set('department', department)
      const headers = { Authorization: `Bearer ${token}` }
      const [attendanceResponse, summaryResponse] = await Promise.all([
        fetch(`${API}/attendance?${params}`, { headers }), fetch(`${API}/attendance/summary?${summaryParams}`, { headers }),
      ])
      const [attendanceData, summaryData] = await Promise.all([attendanceResponse.json().catch(() => []), summaryResponse.json().catch(() => ({}))])
      if (!attendanceResponse.ok) throw new Error(attendanceData?.detail || 'Could not load attendance records.')
      if (!summaryResponse.ok) throw new Error(summaryData?.detail || 'Could not load attendance summary.')
      setRows(attendanceData); setSummary(summaryData.employees || [])
    } catch (error) { notify(error.message, 'error') }
  }, [token, startDate, endDate, monthFilter, department, notify])
  useEffect(() => { Promise.resolve().then(load) }, [load])

  async function saveCorrection(event) {
    event.preventDefault(); setBusy(true)
    try {
      const payload = { ...editing, employee_id: Number(editing.employee_id), check_in: editing.check_in || null, check_out: editing.check_out || null }
      const response = await fetch(`${API}/attendance/override`, { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || 'Attendance correction failed.')
      notify('Attendance correction saved and audit logged.', 'success'); setEditing(null); await load()
    } catch (error) { notify(error.message, 'error') }
    finally { setBusy(false) }
  }

  function startCorrection(row) {
    setEditing({ employee_id: String(row.employee_id), work_date: row.work_date, check_in: localDateTime(row.check_in),
      check_out: localDateTime(row.check_out), status: row.status, correction_note: '' })
  }

  return <section className="panel"><div className="panel-head"><div><h2>Attendance management</h2><p>Review monthly attendance and record audited corrections.</p></div><span className="panel-icon">◷</span></div>
    <div className="employee-form report-filters"><h3>Filters</h3><div className="form-grid"><label>Start date<input type="date" max={endDate} value={startDate} onChange={event => setStartDate(event.target.value)}/></label><label>End date<input type="date" min={startDate} value={endDate} onChange={event => setEndDate(event.target.value)}/></label><label>Summary month<input type="month" value={monthFilter} onChange={event => setMonthFilter(event.target.value)}/></label><label>Department<select value={department} onChange={event => setDepartment(event.target.value)}><option value="">All departments</option>{departments.map(name => <option key={name}>{name}</option>)}</select></label></div></div>
    <h3 className="subheading">Monthly summary · {monthFilter}</h3><div className="table-wrap"><table><thead><tr><th>Employee</th><th>Department</th><th>Present</th><th>Absent</th><th>Leave</th><th>Worked hours</th></tr></thead><tbody>{summary.map(row => <tr key={row.employee_id}><td><strong>{row.employee_name}</strong><small className="block">{row.employee_code}</small></td><td>{row.department}</td><td>{row.attendance_days}</td><td>{row.absent_days}</td><td>{row.leave_days}</td><td>{row.worked_hours}</td></tr>)}{summary.length === 0 && <tr><td colSpan="6" className="empty">No summary data for the selected month.</td></tr>}</tbody></table></div>
    <div className="panel-head section-spaced"><div><h3>Daily records</h3><p>{rows.length} record(s) in selected date range.</p></div><button className="secondary small-btn" onClick={() => { setEditing({ employee_id: employees[0]?.id ? String(employees[0].id) : '', work_date: today, check_in: '', check_out: '', status: 'present', correction_note: '' }) }}>+ Add / correct record</button></div>
    {editing && <form className="employee-form" onSubmit={saveCorrection}><h3>Attendance correction</h3><div className="form-grid"><label>Employee<select required value={editing.employee_id} onChange={event => setEditing({ ...editing, employee_id: event.target.value })}><option value="">Select employee</option>{employees.map(row => <option key={row.id} value={row.id}>{row.full_name} · {row.employee_code}</option>)}</select></label><label>Work date<input type="date" required value={editing.work_date} onChange={event => setEditing({ ...editing, work_date: event.target.value })}/></label><label>Check-in<input type="datetime-local" value={editing.check_in} onChange={event => setEditing({ ...editing, check_in: event.target.value })}/></label><label>Check-out<input type="datetime-local" value={editing.check_out} onChange={event => setEditing({ ...editing, check_out: event.target.value })}/></label><label>Status<select value={editing.status} onChange={event => setEditing({ ...editing, status: event.target.value })}><option value="present">Present</option><option value="absent">Absent</option><option value="leave">Leave</option><option value="half_day">Half day</option></select></label><label>Reason for correction<input required minLength="5" maxLength="500" value={editing.correction_note} onChange={event => setEditing({ ...editing, correction_note: event.target.value })} placeholder="Explain the correction"/></label></div><div className="button-row"><button className="primary" disabled={busy || !editing.employee_id}>{busy ? 'Saving…' : 'Save correction'}</button><button className="secondary" type="button" onClick={() => setEditing(null)}>Cancel</button></div></form>}
    <div className="table-wrap"><table><thead><tr><th>Date</th><th>Employee</th><th>Check-in</th><th>Check-out</th><th>Hours</th><th>Status</th><th>Correction</th><th>Action</th></tr></thead><tbody>{rows.map(row => { const employee = employees.find(item => item.id === row.employee_id); return <tr key={row.id}><td>{row.work_date}</td><td>{employee?.full_name || `Employee #${row.employee_id}`}</td><td>{row.check_in ? localDateTime(row.check_in).slice(11) : '—'}</td><td>{row.check_out ? localDateTime(row.check_out).slice(11) : '—'}</td><td>{row.worked_hours ?? '—'}</td><td><span className={`status ${row.status === 'present' ? 'approved' : row.status === 'absent' ? 'rejected' : 'pending'}`}>{row.status}</span></td><td>{row.correction_note || '—'}</td><td><button className="secondary small-btn" onClick={() => startCorrection(row)}>Correct</button></td></tr> })}{rows.length === 0 && <tr><td colSpan="8" className="empty">No attendance records in this date range.</td></tr>}</tbody></table></div>
  </section>
}
