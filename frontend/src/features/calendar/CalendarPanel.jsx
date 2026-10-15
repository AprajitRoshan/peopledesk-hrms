import { useCallback, useEffect, useMemo, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
const today = new Date()
const toMonth = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
const initialForm = () => ({ name: '', holiday_date: toMonth(today) + '-15', holiday_type: 'company', region: '', department: '', description: '' })
const prettyType = value => ({ company: 'Company-wide', regional: 'Regional', optional: 'Optional' }[value] || value)

async function request(path, { token, method = 'GET', body } = {}) {
  const response = await fetch(`${API}${path}`, { method, headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`)
  return data
}

export default function CalendarPanel({ token, notify, isAdmin = false, compact = false }) {
  const [view, setView] = useState('month')
  const [selectedMonth, setSelectedMonth] = useState(toMonth(today))
  const [year, setYear] = useState(today.getFullYear())
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(initialForm())
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const suffix = view === 'year' ? `?year=${year}` : `?month=${selectedMonth}`
      const data = await request(`/holidays${suffix}`, { token })
      setRows(Array.isArray(data) ? data : [])
    } catch (error) { notify(error.message, 'error') } finally { setLoading(false) }
  }, [token, notify, view, selectedMonth, year])
  useEffect(() => { load() }, [load])

  const monthDate = useMemo(() => { const [y, m] = selectedMonth.split('-').map(Number); return new Date(y, m - 1, 1) }, [selectedMonth])
  const monthGrid = useMemo(() => {
    const first = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
    const startOffset = (first.getDay() + 6) % 7
    const days = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0).getDate()
    return [...Array(startOffset).fill(null), ...Array.from({ length: days }, (_, index) => index + 1)]
  }, [monthDate])
  const rowsByDate = useMemo(() => rows.reduce((result, row) => { (result[row.holiday_date] ||= []).push(row); return result }, {}), [rows])

  async function addHoliday(event) {
    event.preventDefault()
    try {
      await request('/holidays', { token, method: 'POST', body: { ...form, region: form.region.trim() || null, department: form.department.trim() || null, description: form.description.trim() || null } })
      notify('Holiday added to the company calendar.', 'success'); setForm(initialForm()); setShowForm(false); await load()
    } catch (error) { notify(error.message, 'error') }
  }
  async function toggleSelected(row) {
    setBusyId(row.id)
    try {
      await request(`/holidays/${row.id}/select`, { token, method: row.is_selected ? 'DELETE' : 'POST' })
      notify(row.is_selected ? 'Optional holiday selection removed.' : 'Optional holiday selected.', 'success'); await load()
    } catch (error) { notify(error.message, 'error') } finally { setBusyId(null) }
  }
  async function deactivate(row) {
    if (!window.confirm(`Deactivate ${row.name}? The historical record will be retained.`)) return
    try { await request(`/holidays/${row.id}`, { token, method: 'DELETE' }); notify('Holiday deactivated.', 'success'); await load() }
    catch (error) { notify(error.message, 'error') }
  }
  const monthName = monthDate.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

  return <section className={`panel calendar-panel ${compact ? 'compact-panel' : ''}`}>
    <div className="panel-head"><div><h2>{compact ? 'Company calendar' : 'Holiday & calendar management'}</h2><p>{compact ? 'Company, regional and optional holidays.' : 'Manage shared holidays and review a monthly or yearly calendar.'}</p></div><div className="button-row"><button className={view === 'month' ? 'primary small-btn' : 'secondary small-btn'} onClick={() => setView('month')}>Month</button><button className={view === 'year' ? 'primary small-btn' : 'secondary small-btn'} onClick={() => setView('year')}>Year</button>{isAdmin && !compact && <button className="secondary" onClick={() => setShowForm(v => !v)}>{showForm ? 'Cancel' : '+ Add holiday'}</button>}</div></div>
    {showForm && isAdmin && <form className="employee-form" onSubmit={addHoliday}><h3>New holiday</h3><div className="form-grid"><label>Holiday name<input required minLength="2" maxLength="160" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Foundation Day" /></label><label>Date<input type="date" required value={form.holiday_date} onChange={e => setForm({ ...form, holiday_date: e.target.value })} /></label><label>Type<select value={form.holiday_type} onChange={e => setForm({ ...form, holiday_type: e.target.value })}><option value="company">Company-wide</option><option value="regional">Regional</option><option value="optional">Optional</option></select></label><label>Region (regional)<input value={form.region} onChange={e => setForm({ ...form, region: e.target.value })} placeholder="e.g. Bihar" /></label><label>Department scope (optional)<input value={form.department} onChange={e => setForm({ ...form, department: e.target.value })} placeholder="All departments if blank" /></label><label>Description<input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} maxLength="2000" /></label></div>{form.holiday_type === 'regional' && !form.region.trim() && !form.department.trim() && <p className="muted">Regional holidays require a region or department scope.</p>}<button className="primary" type="submit">Save holiday</button></form>}
    <div className="calendar-toolbar"><label>{view === 'year' ? 'Calendar year' : 'Calendar month'}{view === 'year' ? <input type="number" min="2000" max="2200" value={year} onChange={e => setYear(Number(e.target.value))} /> : <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)} />}</label><span>{rows.length} holiday(s) · {loading ? 'Refreshing…' : 'Calendar updated'}</span></div>
    {view === 'month' && <><h3 className="calendar-month-title">{monthName}</h3><div className="calendar-grid calendar-weekdays">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => <div key={day}>{day}</div>)}</div><div className="calendar-grid">{monthGrid.map((day, index) => { const stamp = day ? `${selectedMonth}-${String(day).padStart(2, '0')}` : `blank-${index}`; const items = day ? (rowsByDate[stamp] || []) : []; return <div className={`calendar-day ${day ? '' : 'blank'}`} key={stamp}><span>{day || ''}</span>{items.slice(0, 2).map(row => <small key={row.id} className={`holiday-event ${row.holiday_type}`} title={row.name}>{row.name}</small>)}{items.length > 2 && <small>+{items.length - 2} more</small>}</div> })}</div></>}
    {view === 'year' && <div className="holiday-month-list">{Array.from({ length: 12 }, (_, i) => i + 1).map(month => { const items = rows.filter(row => Number(row.holiday_date.slice(5, 7)) === month); return <article className="holiday-month-card" key={month}><h3>{new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: 'long' })}</h3>{items.length ? items.map(row => <div className="holiday-list-row" key={row.id}><div><strong>{new Date(`${row.holiday_date}T00:00:00`).toLocaleDateString(undefined, { day: '2-digit', month: 'short' })} · {row.name}</strong><small>{prettyType(row.holiday_type)}{row.region ? ` · ${row.region}` : ''}</small></div><span className="status neutral">{row.holiday_date}</span></div>) : <small className="muted">No holidays listed.</small>}</article> })}</div>}
    <div className="subsection"><div className="panel-head"><div><h3>{view === 'year' ? `Holidays in ${year}` : 'Holiday list'}</h3><p>Regional holidays apply when the employee profile region matches. Optional holidays are selected by each employee.</p></div><button className="secondary small-btn" onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button></div><div className="history-list">{rows.map(row => <div className="history-row" key={row.id}><div><strong>{row.name}</strong><small>{row.holiday_date} · {prettyType(row.holiday_type)}{row.region ? ` · ${row.region}` : ''}{row.department ? ` · ${row.department}` : ''}</small>{row.description && <small>{row.description}</small>}</div><div className="action-pair">{row.holiday_type === 'optional' && !isAdmin && <button className={row.is_selected ? 'secondary small-btn' : 'approve-btn'} disabled={busyId === row.id} onClick={() => toggleSelected(row)}>{row.is_selected ? 'Selected · Undo' : 'Select optional'}</button>}{isAdmin && !compact && <button className="reject-btn small-btn" onClick={() => deactivate(row)}>Deactivate</button>}</div></div>)}{rows.length === 0 && <p className="empty">No holidays configured for this view.</p>}</div></div>
  </section>
}
