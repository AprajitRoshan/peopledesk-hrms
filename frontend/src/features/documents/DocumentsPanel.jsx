import { useCallback, useEffect, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
const EMPTY_EMPLOYEES = []

export default function DocumentsPanel({ token, notify, employees = EMPTY_EMPLOYEES, user }) {
  const isManager = ['admin', 'hr'].includes(user?.role)
  const [selfEmployee, setSelfEmployee] = useState(null)
  const [selectedId, setSelectedId] = useState('')
  const [documents, setDocuments] = useState([])
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (isManager) {
      if (!selectedId && employees.length) setSelectedId(String(employees[0].id))
      return
    }
    let active = true
    fetch(`${API}/employees/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async response => { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data?.detail || 'Could not load employee profile.'); return data })
      .then(data => { if (active) { setSelfEmployee(data); setSelectedId(String(data.id)) } })
      .catch(error => notify(error.message, 'error'))
    return () => { active = false }
  }, [token, isManager, employees, selectedId, notify])

  const load = useCallback(async () => {
    if (!selectedId) { setDocuments([]); return }
    try {
      const route = isManager ? `/documents/${selectedId}` : '/documents/me'
      const response = await fetch(`${API}${route}`, { headers: { Authorization: `Bearer ${token}` } })
      const data = await response.json().catch(() => [])
      if (!response.ok) throw new Error(data?.detail || 'Could not load employee documents.')
      setDocuments(data)
    } catch (error) { notify(error.message, 'error') }
  }, [selectedId, isManager, token, notify])
  useEffect(() => { Promise.resolve().then(load) }, [load])

  async function upload(event) {
    event.preventDefault()
    if (!selectedId || !file) return
    setBusy(true)
    try {
      const formData = new FormData(); formData.append('file', file)
      const response = await fetch(`${API}/documents/${selectedId}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: formData })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || 'Document upload failed.')
      setFile(null)
      const input = document.getElementById('hrms-document-file')
      if (input) input.value = ''
      notify('Employee document uploaded securely.', 'success'); await load()
    } catch (error) { notify(error.message, 'error') }
    finally { setBusy(false) }
  }

  async function download(row) {
    try {
      const response = await fetch(`${API}/documents/file/${row.id}`, { headers: { Authorization: `Bearer ${token}` } })
      if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data?.detail || 'Download failed.') }
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = row.original_filename; anchor.click(); URL.revokeObjectURL(url)
    } catch (error) { notify(error.message, 'error') }
  }

  const selectedEmployee = employees.find(row => String(row.id) === selectedId) || selfEmployee
  return <section className="panel"><div className="panel-head"><div><h2>{isManager ? 'Employee documents' : 'My documents'}</h2><p>Upload PDF, PNG or JPEG files up to 5 MB. Files are stored under generated names and require authenticated access to download.</p></div><span className="panel-icon">▣</span></div>
    {isManager && <label className="document-employee-select">Employee<select value={selectedId} onChange={event => setSelectedId(event.target.value)}><option value="">Select employee</option>{employees.map(row => <option key={row.id} value={row.id}>{row.full_name} · {row.employee_code}</option>)}</select></label>}
    {selectedEmployee && <p className="muted">Selected: <strong>{selectedEmployee.full_name}</strong> · {selectedEmployee.employee_code}</p>}
    <form className="employee-form document-upload-form" onSubmit={upload}><h3>Upload document</h3><div className="form-grid"><label className="full-span">Choose file<input id="hrms-document-file" type="file" required accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={event => setFile(event.target.files?.[0] || null)}/></label></div><button className="primary" disabled={busy || !selectedId || !file}>{busy ? 'Uploading…' : 'Upload document'}</button></form>
    <div className="table-tools"><strong>Saved documents</strong><span>{documents.length} file(s)</span></div><div className="table-wrap"><table><thead><tr><th>Filename</th><th>Type</th><th>Size</th><th>Uploaded</th><th>Action</th></tr></thead><tbody>{documents.map(row => <tr key={row.id}><td>{row.original_filename}</td><td>{row.content_type}</td><td>{Math.ceil(row.file_size / 1024)} KB</td><td>{row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</td><td><button type="button" className="secondary small-btn" onClick={() => download(row)}>Download</button></td></tr>)}{documents.length === 0 && <tr><td colSpan="5" className="empty">No documents uploaded yet.</td></tr>}</tbody></table></div>
  </section>
}
