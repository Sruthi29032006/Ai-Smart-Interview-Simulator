import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../App.jsx'

const LEVELS = ['Fresher', '0-1 years', '1-3 years', '3-5 years', '5+ years']

export default function Profile() {
  const [f, setF] = useState(null); const [msg, setMsg] = useState(''); const [err, setErr] = useState(''); const { setUser, user } = useAuth()
  useEffect(() => { api('/profile').then(setF).catch((e) => setErr(e.message)) }, [])
  if (!f) return <div className="center">{err || 'Loading…'}</div>
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => { e.preventDefault(); setMsg(''); setErr('')
    try { const r = await api('/profile', { method: 'PUT', body: f }); setF(r); setUser({ ...user, full_name: r.full_name }); setMsg('Profile saved') } catch (x) { setErr(x.message) } }
  return (
    <form className="card" onSubmit={save}>
      <h2>Candidate profile</h2>
      <div className="grid2">
        <label>Full name<input value={f.full_name} onChange={set('full_name')} required /></label>
        <label>Email<input value={f.email} disabled /></label>
        <label>Education<input value={f.education} onChange={set('education')} placeholder="B.Tech CSE (Data Science)" /></label>
        <label>College / University<input value={f.college} onChange={set('college')} /></label>
        <label>Experience level<select value={f.experience_level} onChange={set('experience_level')}>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select></label>
        <label>Target job role<input value={f.target_role} onChange={set('target_role')} placeholder="Data Scientist" /></label>
        <label>Target company<input value={f.target_company} onChange={set('target_company')} /></label>
        <label>Programming languages<input value={f.languages} onChange={set('languages')} placeholder="Python, SQL" /></label>
      </div>
      <label>Technical skills<textarea rows={3} value={f.skills} onChange={set('skills')} placeholder="Pandas, scikit-learn, statistics, Power BI…" /></label>
      {err && <div className="error">{err}</div>}{msg && <div className="ok">{msg}</div>}
      <button className="btn">Save profile</button>
    </form>
  )
}
