import { useCallback, useEffect, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
const currentPeriod = () => new Date().toISOString().slice(0, 7)
const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(value || 0))

async function downloadSlip(recordId, token, notify) {
  try {
    const response = await fetch(`${API}/payroll/${recordId}/salary-slip.pdf`, { headers: { Authorization: `Bearer ${token}` } })
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data?.detail || `Download failed (${response.status})`)
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `salary-slip-${recordId}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    notify('Salary slip downloaded.', 'success')
  } catch (error) { notify(error.message, 'error') }
}

function PayrollTable({ rows, token, notify, onAdjust, onLock, onCredit }) {
  return <div className="table-wrap"><table><thead><tr><th>Employee</th><th>Period</th><th>Net salary</th><th>Earnings & deductions</th><th>Adjustment</th><th>Status</th><th>Actions</th></tr></thead><tbody>
    {rows.map(row => <tr key={row.id}><td><strong>{row.employee_name}</strong><small className="block">{row.employee_code} · {row.department}</small></td><td>{row.pay_period}</td><td><strong>{money(row.net_salary)}</strong></td><td><small className="block">Basic {money(row.basic_pay)} · Allowances {money(row.allowances)}</small><small className="block">Bonus {money(row.bonus)} · Variable {money(row.variable_pay)}</small><small className="block">Overtime {money(row.overtime_pay)} · Components +{money(row.component_earning_total)} / −{money(row.component_deduction_total)}</small></td><td>{money(row.adjustment_amount)}{row.adjustment_note && <small className="block">{row.adjustment_note}</small>}<small className="block">LOP: {row.lop_days || 0} day(s) · {money(row.lop_deduction || 0)}</small></td><td><span className={`status ${row.status === 'credited' ? 'approved' : row.status === 'locked' ? 'pending' : 'neutral'}`}>{row.status}</span></td><td><div className="action-pair"><button className="secondary small-btn" onClick={() => downloadSlip(row.id, token, notify)}>Download PDF</button>{onAdjust && row.status === 'processed' && <button className="secondary small-btn" onClick={() => onAdjust(row)}>Adjust</button>}{onLock && row.status === 'processed' && <button className="secondary small-btn" onClick={() => onLock(row.id)}>Lock</button>}{onCredit && row.status === 'locked' && <button className="approve-btn" onClick={() => onCredit(row.id)}>Simulate credit</button>}</div></td></tr>)}
    {rows.length === 0 && <tr><td colSpan="7" className="empty">No payroll records found for this period.</td></tr>}
  </tbody></table></div>
}

export function AdminPayrollPanel({ token, notify, employees }) {
  const [rows, setRows] = useState([])
  const [periodFilter, setPeriodFilter] = useState(currentPeriod())
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [adjusting, setAdjusting] = useState(null)
  const [adjustmentBusy, setAdjustmentBusy] = useState(false)
  const [compensationPreview, setCompensationPreview] = useState(null)
  const [compensationPreviewLoading, setCompensationPreviewLoading] = useState(false)
  const [compensationPreviewError, setCompensationPreviewError] = useState('')
  const [form, setForm] = useState({ employee_id: '', pay_period: currentPeriod(), base_salary: '', allowances: '0', bonus: '0', variable_pay: '0', deductions: '0', adjustment_amount: '0', adjustment_note: '' })
  const load = useCallback(async () => {
    try {
      const period = periodFilter ? `?period=${encodeURIComponent(periodFilter)}` : ''
      const response = await fetch(`${API}/payroll${period}`, { headers: { Authorization: `Bearer ${token}` } })
      const data = await response.json().catch(() => [])
      if (!response.ok) throw new Error(data?.detail || 'Could not load payroll records.')
      setRows(data)
    } catch (error) { notify(error.message, 'error') }
  }, [periodFilter, token, notify])
  useEffect(() => { Promise.resolve().then(load) }, [load])

  useEffect(() => {
    if (!showForm || !form.employee_id || !form.pay_period) {
      setCompensationPreview(null)
      setCompensationPreviewError('')
      setCompensationPreviewLoading(false)
      return
    }
    let active = true
    setCompensationPreviewLoading(true)
    setCompensationPreviewError('')
    const query = new URLSearchParams({ employee_id: form.employee_id, period: form.pay_period })
    fetch(`${API}/payroll/compensation-preview?${query.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async response => {
        const data = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(data?.detail || 'Could not load effective compensation.')
        return data
      })
      .then(data => { if (active) setCompensationPreview(data) })
      .catch(error => {
        if (active) { setCompensationPreview(null); setCompensationPreviewError(error.message || 'Could not load effective compensation.') }
      })
      .finally(() => { if (active) setCompensationPreviewLoading(false) })
    return () => { active = false }
  }, [showForm, form.employee_id, form.pay_period, token])

  async function submit(event) {
    event.preventDefault(); setBusy(true)
    try {
      const payload = { ...form, employee_id: Number(form.employee_id), base_salary: (form.base_salary.trim() === '' ? null : Number(form.base_salary)), allowances: Number(form.allowances || 0), bonus: Number(form.bonus || 0), variable_pay: Number(form.variable_pay || 0), deductions: Number(form.deductions || 0), adjustment_amount: Number(form.adjustment_amount || 0), adjustment_note: form.adjustment_note.trim() || null }
      const response = await fetch(`${API}/payroll`, { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || 'Payroll processing failed.')
      notify('Payroll processed. A notification was sent or logged, depending on SMTP settings.', 'success')
      setShowForm(false)
      setForm({ employee_id: '', pay_period: currentPeriod(), base_salary: '', allowances: '0', bonus: '0', variable_pay: '0', deductions: '0', adjustment_amount: '0', adjustment_note: '' })
      setPeriodFilter(payload.pay_period)
      if (payload.pay_period === periodFilter) await load()
    } catch (error) { notify(typeof error.message === 'string' ? error.message : 'Payroll processing failed.', 'error') }
    finally { setBusy(false) }
  }

  async function payrollTransition(recordId, action) {
    const label = action === 'lock' ? 'lock payroll' : 'simulate salary credit'
    if (!window.confirm(`Confirm ${label}? Salary credit is a simulation only; no bank transfer will occur.`)) return
    try {
      const response = await fetch(`${API}/payroll/${recordId}/${action}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || `Could not ${label}.`)
      notify(action === 'lock' ? 'Payroll locked. Adjustments are disabled.' : 'Salary credit simulation recorded.', 'success')
      await load()
    } catch (error) { notify(error.message, 'error') }
  }

  async function saveAdjustment(event) {
    event.preventDefault()
    if (!adjusting) return
    setAdjustmentBusy(true)
    try {
      const response = await fetch(`${API}/payroll/${adjusting.id}/adjustment`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ adjustment_amount: Number(adjusting.adjustment_amount), adjustment_note: adjusting.adjustment_note }) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || 'Could not update salary adjustment.')
      notify('Salary adjustment saved and audit logged.', 'success')
      setAdjusting(null)
      await load()
    } catch (error) { notify(error.message, 'error') }
    finally { setAdjustmentBusy(false) }
  }

  const total = rows.reduce((sum, row) => sum + Number(row.net_salary || 0), 0)
  return <section className="panel"><div className="panel-head"><div><h2>Payroll processing</h2><p>Process monthly salary, record adjustments, and issue salary slips.</p></div><button className="primary" onClick={() => setShowForm(value => !value)}>{showForm ? 'Cancel' : '+ Process payroll'}</button></div>
    <div className="stat-grid payroll-summary"><article className="stat-card"><div className="stat-top">Records processed<span className="stat-icon">▤</span></div><strong>{rows.length}</strong><small>For selected pay period</small></article><article className="stat-card"><div className="stat-top">Net payroll total<span className="stat-icon">₹</span></div><strong>{money(total)}</strong><small>Sum of listed net salaries</small></article></div>
    {showForm && <form className="employee-form" onSubmit={submit}><h3>Process employee salary</h3><div className="form-grid"><label>Employee<select required value={form.employee_id} onChange={event => setForm({ ...form, employee_id: event.target.value })}><option value="">Select employee</option>{employees.filter(employee => employee.employment_status === 'active').map(employee => <option value={employee.id} key={employee.id}>{employee.full_name} · {employee.employee_code}</option>)}</select></label><label>Pay period<input required type="month" value={form.pay_period} onChange={event => setForm({ ...form, pay_period: event.target.value })}/></label><label>Base salary (₹)<input type="number" min="0" step="0.01" value={form.base_salary} onChange={event => setForm({ ...form, base_salary: event.target.value })} placeholder="Use employee profile salary"/></label><label>Allowances (₹)<input type="number" min="0" step="0.01" value={form.allowances} onChange={event => setForm({ ...form, allowances: event.target.value })}/></label><label>Bonus (₹)<input type="number" min="0" step="0.01" value={form.bonus} onChange={event => setForm({ ...form, bonus: event.target.value })}/></label><label>Variable pay (₹)<input type="number" min="0" step="0.01" value={form.variable_pay} onChange={event => setForm({ ...form, variable_pay: event.target.value })}/></label><label>Deductions (₹)<input type="number" min="0" step="0.01" value={form.deductions} onChange={event => setForm({ ...form, deductions: event.target.value })}/></label><label>Manual adjustment (₹)<input type="number" step="0.01" value={form.adjustment_amount} onChange={event => setForm({ ...form, adjustment_amount: event.target.value })}/></label><label className="full-span">Adjustment note (required when adjustment is non-zero)<input maxLength="500" value={form.adjustment_note} onChange={event => setForm({ ...form, adjustment_note: event.target.value })} placeholder="e.g. approved overtime or correction"/></label></div>{compensationPreviewLoading && <p className="muted">Checking compensation effective for {form.pay_period}…</p>}{compensationPreviewError && <p className="alert error">{compensationPreviewError}</p>}{compensationPreview && <div className="note-box payroll-compensation-preview"><h4>Effective compensation for {compensationPreview.pay_period}</h4><p><strong>Source:</strong> {compensationPreview.salary_source === 'compensation_revision' ? `Revision #${compensationPreview.revision_id}` : 'Employee profile salary'}{compensationPreview.effective_from ? ` · Effective ${compensationPreview.effective_from}${compensationPreview.effective_to ? ` through ${compensationPreview.effective_to}` : ' onward'}` : ''}</p><p><strong>Base:</strong> {money(compensationPreview.base_salary)} · <strong>Basic breakdown:</strong> {money(compensationPreview.basic_pay)} · <strong>Revision allowances:</strong> {money(compensationPreview.allowances)}</p><p><strong>Configured earnings:</strong> +{money(compensationPreview.component_earning_total)} · <strong>Configured deductions:</strong> −{money(compensationPreview.component_deduction_total)}</p>{compensationPreview.configured_components?.length > 0 && <p><strong>Components:</strong> {compensationPreview.configured_components.map(item => `${item.name} ${item.component_type === 'deduction' ? '−' : '+'}${money(item.amount)}`).join(' · ')}</p>}<p><strong>LOP:</strong> {compensationPreview.lop_days} day(s), −{money(compensationPreview.lop_deduction)} · <strong>Estimated net:</strong> {money(compensationPreview.estimated_net_salary)} <span>(before manual form entries)</span></p>{compensationPreview.warnings?.map((warning, index) => <p className="alert error" key={index}>{warning}</p>)}{compensationPreview.payroll_already_exists && <p className="alert error">Payroll already exists for this employee and period. Duplicate processing will be blocked.</p>}</div>}<p className="muted payroll-formula">The effective compensation revision for the first day of the selected pay period is shown above. Leave Base salary blank to use that revision. Approved unpaid leave days generate an automatic LOP deduction based on weekdays in the month. Net salary = base + allowances + bonus + variable pay + configured earnings + overtime + adjustment − other deductions − configured deductions − LOP deduction. Duplicate employee/pay-period records are blocked.</p><button className="primary" disabled={busy || employees.filter(employee => employee.employment_status === 'active').length === 0 || Boolean(compensationPreview?.payroll_already_exists)}>{busy ? 'Processing…' : 'Process salary and create slip'}</button></form>}
    {adjusting && <form className="employee-form" onSubmit={saveAdjustment}><h3>Adjust salary · {adjusting.employee_name} ({adjusting.pay_period})</h3><div className="form-grid"><label>Adjustment amount (₹)<input required type="number" step="0.01" value={adjusting.adjustment_amount} onChange={event => setAdjusting({ ...adjusting, adjustment_amount: event.target.value })}/></label><label>Reason for adjustment<input required minLength="3" maxLength="500" value={adjusting.adjustment_note} onChange={event => setAdjusting({ ...adjusting, adjustment_note: event.target.value })}/></label></div><div className="button-row"><button className="primary" disabled={adjustmentBusy}>{adjustmentBusy ? 'Saving…' : 'Save adjustment'}</button><button type="button" className="secondary" onClick={() => setAdjusting(null)}>Cancel</button></div></form>}
    <div className="table-tools"><label>Pay period <input type="month" value={periodFilter} onChange={event => setPeriodFilter(event.target.value)} /></label><span>{rows.length} records</span></div>
    <PayrollTable rows={rows} token={token} notify={notify} onAdjust={row => setAdjusting({ ...row, adjustment_amount: String(row.adjustment_amount ?? 0), adjustment_note: row.adjustment_note || '' })} onLock={id => payrollTransition(id, 'lock')} onCredit={id => payrollTransition(id, 'credit')}/>
  </section>
}

export function EmployeePayslips({ token, notify }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    fetch(`${API}/payroll/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async response => { const data = await response.json().catch(() => []); if (!response.ok) throw new Error(data?.detail || 'Could not load salary slips.'); return data })
      .then(data => { if (active) setRows(data) })
      .catch(error => notify(error.message, 'error'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token, notify])
  return <section className="panel payslip-panel"><div className="panel-head"><div><h2>My salary slips</h2><p>Download your processed monthly salary statements.</p></div><span className="panel-icon">₹</span></div>{loading ? <p className="loading-line">Loading salary slips…</p> : <PayrollTable rows={rows} token={token} notify={notify}/>}</section>
}
