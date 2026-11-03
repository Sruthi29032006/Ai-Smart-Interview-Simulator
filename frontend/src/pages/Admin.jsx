import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Admin() {
  const [s, setS] = useState(null); const [users, setUsers] = useState([]); const [sys, setSys] = useState(null); const [cats, setCats] = useState([]); const [nc, setNc] = useState(''); const [err, setErr] = useState('')
  const load = () => Promise.all([api('/admin/stats'), api('/admin/users'), api('/admin/system'), api('/admin/categories')])
    .then(([a, b, c, d]) => { setS(a); setUsers(b); setSys(c); setCats(d) }).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  const toggle = async (c) => { await api(`/admin/categories/${c.id}`, { method: 'PUT', body: { name: c.name, enabled: !c.enabled } }); load() }
  const add = async (e) => { e.preventDefault(); try { await api('/admin/categories', { method: 'POST', body: { name: nc } }); setNc(''); load() } catch (x) { setErr(x.message) } }
  if (!s) return <div className="center">{err || 'Loading…'}</div>
  return (
    <div><h2>Admin dashboard</h2>{err && <div className="error">{err}</div>}
      <p className="small muted">Aggregate data only. Candidate recordings, transcripts and reports are not accessible from here.</p>
      <div className="grid4">
        <div className="card stat"><b>{s.users}</b><span>Users</span></div>
        <div className="card stat"><b>{s.interviews.completed || 0}</b><span>Completed interviews</span></div>
        <div className="card stat"><b>{s.answers_evaluated}</b><span>Answers evaluated</span></div>
        <div className="card stat"><b>{s.avg_score ? s.avg_score.toFixed(1) : '-'}</b><span>Average score</span></div>
      </div>
      <div className="grid2">
        <div className="card"><h3>System health</h3><ul>
          <li>LLM: {sys.llm_provider} / {sys.llm_model} — <b className={sys.llm_configured ? 'okc' : 'badc'}>{sys.llm_configured ? 'API key configured' : 'NOT configured'}</b></li>
          <li>Speech model: {sys.whisper_model}</li>
          <li>Face landmarker model: <b className={sys.face_landmarker_model_present ? 'okc' : 'badc'}>{sys.face_landmarker_model_present ? 'present' : 'missing (basic face detection only)'}</b></li>
          <li>Free disk: {sys.disk_free_gb} GB · Recording retention: {sys.retention_days || 'unlimited'} days</li></ul>
          <h4>Interviews by status</h4><ul>{Object.entries(s.interviews).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul></div>
        <div className="card"><h3>Interview categories</h3>
          <table><tbody>{cats.map((c) => <tr key={c.id}><td>{c.name}</td><td><button className="link" onClick={() => toggle(c)}>{c.enabled ? 'Enabled (disable)' : 'Disabled (enable)'}</button></td></tr>)}</tbody></table>
          <form className="row" onSubmit={add}><input placeholder="New category" value={nc} onChange={(e) => setNc(e.target.value)} required /><button className="btn small">Add</button></form>
          <h4>Usage by category</h4><ul>{Object.entries(s.by_type).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul></div>
      </div>
      <div className="card"><h3>Registered users</h3><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Joined</th><th>Interviews</th></tr></thead><tbody>
        {users.map((u) => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{new Date(u.joined + 'Z').toLocaleDateString()}</td><td>{u.interviews}</td></tr>)}</tbody></table></div>
    </div>
  )
}
