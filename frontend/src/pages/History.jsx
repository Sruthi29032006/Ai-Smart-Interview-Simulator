import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadPdf } from '../api.js'
import { Bar, LABELS } from '../components.jsx'

export default function History() {
  const [list, setList] = useState(null); const [err, setErr] = useState(''); const [sel, setSel] = useState([]); const [cmp, setCmp] = useState(null)
  const load = () => api('/interviews').then(setList).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  const del = async (id) => { if (!confirm('Delete this interview, its transcripts and recordings permanently?')) return; await api(`/interviews/${id}`, { method: 'DELETE' }); setSel(sel.filter((x) => x !== id)); load() }
  const toggle = (id) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id].slice(-2))
  const compare = async () => setCmp(await Promise.all(sel.map((id) => api(`/interviews/${id}`))))
  if (!list) return <div className="center">{err || 'Loading…'}</div>
  return (
    <div>
      <div className="row between"><h2>Interview history</h2><button className="btn secondary" disabled={sel.length !== 2} onClick={compare}>Compare selected (2)</button></div>
      {err && <div className="error">{err}</div>}
      <div className="card">{list.length === 0 ? <p>No interviews yet.</p> : <table><thead><tr><th /><th>Date</th><th>Type</th><th>Difficulty</th><th>Answered</th><th>Duration</th><th>Status</th><th>Score</th><th /></tr></thead><tbody>
        {list.map((i) => <tr key={i.id}>
          <td>{i.status === 'completed' && <input type="checkbox" checked={sel.includes(i.id)} onChange={() => toggle(i.id)} />}</td>
          <td>{new Date(i.started_at + 'Z').toLocaleString()}</td><td>{i.type}</td><td>{i.difficulty}</td><td>{i.answered}/{i.question_count}</td>
          <td>{i.duration_sec ? `${Math.round(i.duration_sec / 60)} min` : '-'}</td><td>{i.status}</td><td>{i.overall_score ?? '-'}</td>
          <td className="actions">{i.status === 'completed' && <><Link to={`/report/${i.id}`}>Open</Link> <button className="link" onClick={() => downloadPdf(i.id)}>PDF</button></>}
            {i.status === 'active' && <Link to={`/interview/${i.id}`}>Resume</Link>} <button className="link danger-text" onClick={() => del(i.id)}>Delete</button></td></tr>)}</tbody></table>}</div>
      {cmp && <div className="card"><h3>Comparison</h3><div className="grid2">{cmp.map((c) => (
        <div key={c.id}><h4>{c.type} · {new Date(c.started_at + 'Z').toLocaleDateString()} · {c.overall_score}/100</h4>
          {Object.keys(LABELS).map((k) => <Bar key={k} label={LABELS[k]} value={c.report?.category_scores?.[k] ?? null} />)}</div>))}</div></div>}
    </div>
  )
}
