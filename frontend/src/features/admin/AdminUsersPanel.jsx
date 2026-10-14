import { useCallback, useEffect, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

export default function AdminUsersPanel({ token, notify, currentUser }) {
  const [users, setUsers] = useState([])
  const [search, setSearch] = useState('')
  const [busyId, setBusyId] = useState(null)
  const load = useCallback(async () => {
    try {
      const query = search ? `?search=${encodeURIComponent(search)}` : ''
      const response = await fetch(`${API}/admin/users${query}`, { headers: { Authorization: `Bearer ${token}` } })
      const data = await response.json().catch(() => [])
      if (!response.ok) throw new Error(data?.detail || 'Could not load user accounts.')
      setUsers(data)
    } catch (error) { notify(error.message, 'error') }
  }, [token, search, notify])
  useEffect(() => { Promise.resolve().then(load) }, [load])

  async function update(id, route, body, successMessage) {
    setBusyId(id)
    try {
      const response = await fetch(`${API}/admin/users/${id}/${route}`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || 'User update failed.')
      notify(successMessage, 'success'); await load()
    } catch (error) { notify(error.message, 'error') }
    finally { setBusyId(null) }
  }

  return <section className="panel"><div className="panel-head"><div><h2>Role &amp; permission management</h2><p>Only an active administrator can change roles or account access.</p></div><span className="status neutral">Admin only</span></div>
    <div className="table-tools"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search name, email or employee code…"/><span>{users.length} accounts</span></div>
    <div className="table-wrap"><table><thead><tr><th>User</th><th>Employee</th><th>Role</th><th>Account</th><th>Actions</th></tr></thead><tbody>
      {users.map(user => <tr key={user.id}><td><div className="person-cell"><div className="table-avatar">{user.full_name?.charAt(0)?.toUpperCase()}</div><div><strong>{user.full_name}</strong><small>{user.email}</small></div></div></td><td>{user.employee_code || '—'}<small className="block">{user.department || ''}</small></td><td><select aria-label={`Role for ${user.full_name}`} value={user.role} disabled={busyId === user.id || user.id === currentUser.id} onChange={event => update(user.id, 'role', { role: event.target.value }, 'Role updated.') }><option value="employee">Employee</option><option value="hr">HR</option><option value="admin">Admin</option></select></td><td><span className={`status ${user.is_active ? 'approved' : 'rejected'}`}>{user.is_active ? 'Active' : 'Disabled'}</span></td><td><button className={user.is_active ? 'reject-btn' : 'approve-btn'} disabled={busyId === user.id || user.id === currentUser.id} onClick={() => update(user.id, 'status', { is_active: !user.is_active }, user.is_active ? 'Account disabled.' : 'Account enabled.')}>{user.is_active ? 'Disable' : 'Enable'}</button></td></tr>)}
      {users.length === 0 && <tr><td colSpan="5" className="empty">No accounts found.</td></tr>}
    </tbody></table></div>
    <p className="muted small-note">The current account cannot change its own role or disable itself from this screen. The backend also prevents removal of the last active administrator.</p>
  </section>
}
