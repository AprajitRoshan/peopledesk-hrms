import { useCallback, useEffect, useMemo, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

function StatusPill({ status }) {
  const value = String(status || 'unknown').toLowerCase()
  const label = value === 'sent' ? 'Sent' : value === 'failed' ? 'Failed' : value === 'logged' ? 'Logged only' : value
  return <span className={`status notification-status ${value}`}>{label}</span>
}

function prettyTemplate(value) {
  return String(value || '—').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export default function NotificationLogPanel({ token, notify }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [templateFilter, setTemplateFilter] = useState('all')
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API}/payroll/notifications?limit=500`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await response.json().catch(() => [])
      if (!response.ok) throw new Error(data?.detail || `Could not load notification history (${response.status}).`)
      setRows(Array.isArray(data) ? data : [])
    } catch (error) {
      notify(error.message || 'Could not load notification history.', 'error')
    } finally {
      setLoading(false)
    }
  }, [token, notify])

  useEffect(() => { load() }, [load])

  const templates = useMemo(() => [...new Set(rows.map((row) => row.template_key).filter(Boolean))].sort(), [rows])
  const counts = useMemo(() => rows.reduce((result, row) => {
    const status = String(row.status || 'unknown').toLowerCase()
    result[status] = (result[status] || 0) + 1
    return result
  }, {}), [rows])
  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return rows.filter((row) => {
      if (statusFilter !== 'all' && String(row.status).toLowerCase() !== statusFilter) return false
      if (templateFilter !== 'all' && row.template_key !== templateFilter) return false
      if (!query) return true
      return [row.recipient, row.template_key, row.subject, row.related_entity_type, row.related_entity_id, row.error_message]
        .some((value) => String(value ?? '').toLowerCase().includes(query))
    })
  }, [rows, statusFilter, templateFilter, search])

  return <section className="panel notification-log-panel">
    <div className="panel-head">
      <div>
        <h2>Notification log</h2>
        <p>Delivery attempts for onboarding, leave decisions, payroll, and salary slips.</p>
      </div>
      <button className="secondary" onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh log'}</button>
    </div>

    <div className="notification-summary-grid">
      <article className="notification-summary"><span>All attempts</span><strong>{rows.length}</strong><small>Newest entries first</small></article>
      <article className="notification-summary"><span>Sent successfully</span><strong>{counts.sent || 0}</strong><small>Email accepted by configured SMTP</small></article>
      <article className="notification-summary"><span>Logged / failed</span><strong>{(counts.logged || 0) + (counts.failed || 0)}</strong><small>Logged means SMTP is not configured</small></article>
    </div>

    <div className="notification-filters">
      <label>Delivery status
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">All statuses</option>
          <option value="sent">Sent</option>
          <option value="logged">Logged only</option>
          <option value="failed">Failed</option>
        </select>
      </label>
      <label>Notification type
        <select value={templateFilter} onChange={(event) => setTemplateFilter(event.target.value)}>
          <option value="all">All templates</option>
          {templates.map((template) => <option value={template} key={template}>{prettyTemplate(template)}</option>)}
        </select>
      </label>
      <label className="notification-search">Search
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Recipient, subject, event…" />
      </label>
      <span className="notification-result-count">{filteredRows.length} of {rows.length} records</span>
    </div>

    {loading && rows.length === 0 ? <div className="loading-line">Loading notification history…</div> :
      <div className="table-wrap"><table className="notification-table">
        <thead><tr><th>Created</th><th>Status</th><th>Recipient</th><th>Notification</th><th>Subject</th><th>Related item</th><th>Delivery details</th></tr></thead>
        <tbody>
          {filteredRows.map((row) => <tr key={row.id}>
            <td className="mono notification-time">{row.created_at ? new Date(row.created_at).toLocaleString() : '—'}</td>
            <td><StatusPill status={row.status} /></td>
            <td>{row.recipient || '—'}</td>
            <td>{prettyTemplate(row.template_key)}</td>
            <td className="notification-subject">{row.subject || '—'}</td>
            <td>{row.related_entity_type ? `${row.related_entity_type}${row.related_entity_id ? ` #${row.related_entity_id}` : ''}` : '—'}</td>
            <td className="notification-error">{row.status === 'failed' ? (row.error_message || 'Email delivery failed; no error details returned.') : row.status === 'logged' ? 'Email was not sent because SMTP is not configured.' : row.status === 'sent' ? 'SMTP accepted the message.' : (row.error_message || '—')}</td>
          </tr>)}
          {filteredRows.length === 0 && <tr><td colSpan="7" className="empty">{loading ? 'Refreshing notification history…' : 'No notifications match these filters.'}</td></tr>}
        </tbody>
      </table></div>
    }
    <p className="muted notification-log-note">This screen is read-only. “Logged only” records confirm an attempt was recorded, not that an email was delivered. Configure SMTP to send messages and record sent/failed outcomes.</p>
  </section>
}
