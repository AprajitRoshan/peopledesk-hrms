import { useCallback, useEffect, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
const today = new Date().toISOString().slice(0, 10)
const firstOfMonth = `${today.slice(0, 7)}-01`

export default function ReportsPanel({ token, notify, employees = [] }) {
  const [startDate, setStartDate] = useState(firstOfMonth)
  const [endDate, setEndDate] = useState(today)
  const [department, setDepartment] = useState('')
  const [period, setPeriod] = useState(today.slice(0, 7))
  const [summary, setSummary] = useState(null)
  const [busy, setBusy] = useState('')

  const queryForDates = useCallback(() => {
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate })
    if (department) params.set('department', department)
    return params.toString()
  }, [startDate, endDate, department])

  const loadSummary = useCallback(async () => {
    try {
      const response = await fetch(`${API}/reports/summary?${queryForDates()}&period=${encodeURIComponent(period)}`, { headers: { Authorization: `Bearer ${token}` } })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || 'Unable to load report summary.')
      setSummary(data)
    } catch (error) { notify(error.message, 'error') }
  }, [queryForDates, period, token, notify])

  useEffect(() => { Promise.resolve().then(loadSummary) }, [loadSummary])

  async function downloadReport(report, format) {
    const key = `${report}-${format}`
    setBusy(key)
    try {
      let query = report === 'payroll' ? new URLSearchParams({ period }) : new URLSearchParams({ start_date: startDate, end_date: endDate })
      if (department) query.set('department', department)
      const response = await fetch(`${API}/reports/${report}.${format}?${query}`, { headers: { Authorization: `Bearer ${token}` } })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail || `Could not export ${report} report.`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${report}_report.${format}`
      document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url)
      notify(`${report[0].toUpperCase()}${report.slice(1)} ${format.toUpperCase()} downloaded.`, 'success')
    } catch (error) { notify(error.message, 'error') }
    finally { setBusy('') }
  }

  const departments = [...new Set(employees.map(employee => employee.department).filter(Boolean))].sort()
  return <section className="panel">
    <div className="panel-head"><div><h2>Reports &amp; analytics</h2><p>Filter attendance and leave by date, and payroll by pay period. Export to CSV or PDF.</p></div><span className="panel-icon">▤</span></div>
    <div className="employee-form report-filters"><h3>Report filters</h3><div className="form-grid">
      <label>Start date<input type="date" value={startDate} max={endDate} onChange={event => setStartDate(event.target.value)} /></label>
      <label>End date<input type="date" value={endDate} min={startDate} onChange={event => setEndDate(event.target.value)} /></label>
      <label>Department<select value={department} onChange={event => setDepartment(event.target.value)}><option value="">All departments</option>{departments.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Payroll period<input type="month" value={period} onChange={event => setPeriod(event.target.value)} /></label>
    </div></div>
    <div className="stat-grid"><article className="stat-card"><div className="stat-top">Attendance records<span className="stat-icon">◷</span></div><strong>{summary?.attendance_records ?? '—'}</strong><small>{startDate} to {endDate}</small></article><article className="stat-card"><div className="stat-top">Leave requests<span className="stat-icon">▤</span></div><strong>{summary?.leave_requests ?? '—'}</strong><small>{summary?.pending_leaves ?? 0} pending · {summary?.approved_leaves ?? 0} approved</small></article><article className="stat-card"><div className="stat-top">Net payroll<span className="stat-icon">₹</span></div><strong>{summary ? `₹${Number(summary.net_payroll_total || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}</strong><small>{summary?.payroll_records ?? 0} record(s) · {period}</small></article></div>
    <div className="report-list">{[
      { key: 'attendance', title: 'Attendance report', detail: 'Daily check-in/out, worked hours, corrections, and status.', dateBased: true },
      { key: 'leaves', title: 'Leave report', detail: 'Leave type, requested dates, approval status, and review note.', dateBased: true },
      { key: 'payroll', title: 'Payroll summary', detail: 'Earnings, deductions, LOP, adjustments, net pay, and lock/credit status.', dateBased: false },
    ].map(report => <div className="report-row" key={report.key}><div><strong>{report.title}</strong><p>{report.detail}</p></div><div className="action-pair"><button className="secondary small-btn" disabled={Boolean(busy)} onClick={() => downloadReport(report.key, 'csv')}>{busy === `${report.key}-csv` ? 'Exporting…' : 'CSV'}</button><button className="secondary small-btn" disabled={Boolean(busy)} onClick={() => downloadReport(report.key, 'pdf')}>{busy === `${report.key}-pdf` ? 'Exporting…' : 'PDF'}</button></div></div>)}</div>
  </section>
}
