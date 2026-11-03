import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from 'recharts'
import { api, downloadPdf, fetchBlobUrl } from '../api.js'
import { AnswerFeedback, Bar, LABELS } from '../components.jsx'

function Recording({ a }) {
  const [url, setUrl] = useState(''); const [err, setErr] = useState('')
  if (!a.has_media) return null
  const load = async () => { try { setUrl(await fetchBlobUrl(`/interviews/answers/${a.id}/media`)) } catch (e) { setErr(e.message) } }
  const del = async () => { if (confirm('Delete this recording permanently? The transcript and scores are kept.')) { await api(`/interviews/answers/${a.id}/media`, { method: 'DELETE' }); location.reload() } }
  return <div className="box"><h5>🎬 Recording</h5>{url ? <video src={url} controls className="pb" /> : <button className="btn secondary small" onClick={load}>Load recording</button>}
    <button className="link danger-text small" onClick={del}>Delete recording</button>{err && <span className="error">{err}</span>}</div>
}

export default function Report() {
  const { id } = useParams(); const [d, setD] = useState(null); const [err, setErr] = useState(''); const [open, setOpen] = useState(null)
  useEffect(() => { api(`/interviews/${id}`).then(setD).catch((e) => setErr(e.message)) }, [id])
  if (!d) return <div className="center">{err || 'Loading…'}</div>
  const r = d.report
  if (!r) return <div className="card">This interview ended without any evaluated answers, so no report was generated. <Link to="/history">Back</Link></div>
  const cats = Object.keys(LABELS)
  const radar = cats.filter((k) => r.category_scores[k] != null).map((k) => ({ k: LABELS[k], v: r.category_scores[k] }))
  return (
    <div>
      <div className="row between"><h2>Interview report</h2><div className="row"><button className="btn" onClick={() => downloadPdf(d.id)}>⬇ Download PDF</button><Link className="btn secondary" to="/history">History</Link></div></div>
      <div className="card">
        <div className="row wrap"><div className="scorebig">{d.overall_score}<small>/100</small></div>
          <div><b>{d.type}</b> · {d.difficulty} · {d.target_role || 'no role set'}<br />{new Date(d.started_at + 'Z').toLocaleString()} · {Math.round((d.duration_sec || 0) / 60)} min · {r.answered}/{r.total_questions} answered
            {r.previous_average != null && <><br />Your previous average: {r.previous_average}</>}</div></div>
        <p>{r.summary}</p>
        <p className="small muted">{r.weighting_note} Weights used: {Object.entries(r.weights_used).map(([k, v]) => `${LABELS[k]} ${Math.round(v * 100)}%`).join(', ')}.</p>
      </div>
      <div className="grid2">
        <div className="card"><h3>Category scores</h3>{cats.map((k) => <Bar key={k} label={LABELS[k]} value={r.category_scores[k]} />)}</div>
        <div className="card">{radar.length >= 3 ? <ResponsiveContainer width="100%" height={280}><RadarChart data={radar}><PolarGrid /><PolarAngleAxis dataKey="k" tick={{ fontSize: 11 }} /><Radar dataKey="v" stroke="#2563eb" fill="#2563eb" fillOpacity={0.35} /></RadarChart></ResponsiveContainer> : <p className="muted">Radar chart needs at least 3 measured categories.</p>}</div>
      </div>
      <div className="grid2">
        <div className="card good"><h3>Strengths</h3><ul>{r.strengths.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        <div className="card bad"><h3>Weaknesses</h3><ul>{r.weaknesses.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        <div className="card"><h3>Areas for improvement</h3><ul>{r.improvements.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        <div className="card"><h3>Next interview</h3><ul>{r.next_interview_recommendations.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
      </div>
      <p className="small muted">Speech and visual metrics are coaching signals only. They do not measure emotion, honesty, personality or job suitability.</p>
      <div className="card"><h3>Question by question</h3>
        {d.questions.map((q) => (
          <div key={q.id} className="qrow">
            <div className="row between pointer" onClick={() => setOpen(open === q.id ? null : q.id)}>
              <span><b>Q{q.number}.</b> {q.text.slice(0, 110)}{q.text.length > 110 ? '…' : ''} {q.is_followup && <span className="chip">follow-up</span>}</span>
              <b>{q.answer?.status === 'evaluated' ? `${q.answer.score}/100` : 'not answered'}</b></div>
            {open === q.id && <div><p>{q.text}</p>
              {q.answer && <><div className="box"><h5>Your answer ({q.answer.mode === 'voice' ? 'spoken, transcribed' : 'typed'})</h5><p>{q.answer.transcript}</p></div>
                <Recording a={q.answer} />{q.answer.status === 'evaluated' && <AnswerFeedback q={q} />}</>}</div>}
          </div>))}
      </div>
    </div>
  )
}
