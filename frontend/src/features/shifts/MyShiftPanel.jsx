import { useCallback, useEffect, useState } from 'react'
const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')
export default function MyShiftPanel({ token, notify }) {
  const [data,setData]=useState(null)
  const load=useCallback(async()=>{try{const r=await fetch(`${API}/shifts/me/current`,{headers:{Authorization:`Bearer ${token}`}});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d?.detail||'Could not load assigned shift.');setData(d)}catch(e){notify(e.message,'error')}},[token,notify])
  useEffect(()=>{load()},[load])
  const s=data?.shift
  return <section className="panel my-shift-panel"><div className="panel-head"><div><h2>My work schedule</h2><p>Assigned shift and attendance rules for today.</p></div><button className="secondary small-btn" onClick={load}>Refresh</button></div>{s?<div className="my-shift-card"><div className="shift-big-icon">◷</div><div className="shift-big-details"><span className="status neutral">{s.shift_type}</span><h3>{s.name}</h3><strong>{s.start_time} — {s.end_time}</strong><p className="muted">{s.description||'Assigned company work schedule.'}</p><div className="shift-facts"><span>{s.grace_minutes} min check-in grace</span><span>{s.break_minutes} min break</span><span>Overtime after {s.overtime_after_minutes} min</span></div></div></div>:<p className="empty">No active shift is assigned to your profile or department yet.</p>}</section>
}
