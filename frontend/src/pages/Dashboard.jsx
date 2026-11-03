import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, BarChart, Bar as RBar } from 'recharts'
import { api } from '../api.js'

const COLORS = { overall: '#2563eb', technical: '#16a34a', communication: '#f59e0b', speaking: '#9333ea', visual: '#0891b2' }

export default function Dashboard() {
  const [d, setD] = useState(null); const [err, setErr] = useState(''); const [type, setType] = useState('all')
  useEffect(() => { api('/analytics/summary').then(setD).catch((e) => setErr(e.message)) }, [])
  if (!d) return <div className="center">{err || 'Loading…'}</div>
  const trend = d.trend.filter((t) => type === 'all' || t.type === type)
  return (
    <div>
      <div className="row between"><h2>Dashboard</h2><Link className="btn" to="/setup">+ New interview</Link></div>
      <div className="grid4">
        <div className="card stat"><b>{d.completed}</b><span>Completed interviews</span></div>
        <div className="card stat"><b>{d.attempts}</b><span>Total attempts</span></div>
        <div className="card stat"><b>{d.average_score ?? '-'}</b><span>Average score</span></div>
        <div className="card stat"><b>{trend.length > 1 ? `${(trend.at(-1).overall - trend[0].overall).toFixed(1)}` : '-'}</b><span>Change since first interview</span></div>
      </div>
      {d.completed === 0 ? <div className="card">No completed interviews yet. <Link to="/setup">Start your first interview</Link> and your analytics will appear here.</div> : (<>
        <div className="card">
          <div className="row between"><h3>Performance trends</h3>
            <select value={type} onChange={(e) => setType(e.target.value)}><option value="all">All interview types</option>{d.types.map((t) => <option key={t}>{t}</option>)}</select></div>
          <ResponsiveContainer width="100%" height={280}><LineChart data={trend}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" /><YAxis domain={[0, 100]} /><Tooltip /><Legend />
            {Object.entries(COLORS).map(([k, c]) => <Line key={k} type="monotone" dataKey={k} stroke={c} strokeWidth={k === 'overall' ? 3 : 1.5} connectNulls />)}</LineChart></ResponsiveContainer>
          <p className="small muted">Speaking and visual lines appear only for interviews where those were actually measured.</p>
        </div>
        <div className="grid2">
          <div className="card"><h3>Score by difficulty</h3><ResponsiveContainer width="100%" height={220}><BarChart data={d.difficulty}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis domain={[0, 100]} /><Tooltip /><RBar dataKey="score" fill="#2563eb" /></BarChart></ResponsiveContainer></div>
          <div className="card"><h3>Score by topic / skill</h3><ResponsiveContainer width="100%" height={220}><BarChart data={d.skills} layout="vertical"><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" domain={[0, 100]} /><YAxis type="category" dataKey="name" width={130} /><Tooltip /><RBar dataKey="score" fill="#16a34a" /></BarChart></ResponsiveContainer></div>
        </div></>)}
      <div className="card"><h3>Recent interviews</h3>
        {d.recent.length === 0 ? <p className="muted">None yet.</p> : <table><thead><tr><th>Date</th><th>Type</th><th>Status</th><th>Score</th><th /></tr></thead><tbody>
          {d.recent.map((i) => <tr key={i.id}><td>{new Date(i.started_at + 'Z').toLocaleString()}</td><td>{i.type}</td><td>{i.status}</td><td>{i.overall_score ?? '-'}</td>
            <td>{i.status === 'completed' ? <Link to={`/report/${i.id}`}>Report</Link> : i.status === 'active' ? <Link to={`/interview/${i.id}`}>Resume</Link> : ''}</td></tr>)}</tbody></table>}
      </div>
    </div>
  )
}
