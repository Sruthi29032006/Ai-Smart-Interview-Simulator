import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

export default function Setup() {
  const [cats, setCats] = useState([]); const [p, setP] = useState(null); const nav = useNavigate()
  const [f, setF] = useState({ interview_type: 'Data Science Interview', difficulty: 'Mixed', adaptive: false, num_questions: 5, extra: '', consent: false })
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => { api('/categories').then(setCats); api('/profile').then(setP) }, [])
  if (!p) return <div className="center">Loading…</div>
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const start = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try {
      const iv = await api('/interviews', { method: 'POST', body: { interview_type: f.interview_type, difficulty: f.difficulty,
        num_questions: f.adaptive ? 0 : Number(f.num_questions), extra: f.extra, consent_recording: f.consent } })
      nav(`/interview/${iv.id}`, { state: { iv } })
    } catch (x) { setErr(x.message); setBusy(false) }
  }
  return (
    <form className="card" onSubmit={start}>
      <h2>Configure your interview</h2>
      {!p.target_role && <div className="warn">Your profile has no target role yet. Questions will be more relevant if you complete your profile first.</div>}
      <p className="muted small">Profile used: {p.target_role || 'role not set'} {p.target_company && `@ ${p.target_company}`} · {p.experience_level} · Skills: {p.skills || 'not set'}</p>
      <div className="grid2">
        <label>Interview type<select value={f.interview_type} onChange={set('interview_type')}>{cats.map((c) => <option key={c}>{c}</option>)}</select></label>
        <label>Difficulty<select value={f.difficulty} onChange={set('difficulty')}>{['Basic', 'Intermediate', 'Advanced', 'Mixed'].map((d) => <option key={d}>{d}</option>)}</select></label>
        <label>Number of questions<input type="number" min={1} disabled={f.adaptive} value={f.num_questions} onChange={set('num_questions')} /></label>
        <label className="check"><input type="checkbox" checked={f.adaptive} onChange={set('adaptive')} /> Adaptive: keep going until I end the interview</label>
      </div>
      <label>Additional preparation requirements (optional)<textarea rows={2} value={f.extra} onChange={set('extra')} placeholder="e.g. focus on A/B testing and feature engineering" /></label>
      <div className="consent">
        <h4>Camera &amp; microphone consent</h4>
        <ul className="small">
          <li>Your browser records video and audio of each answer <b>only while the red REC indicator is on</b>, and you can stop at any time.</li>
          <li>The recording is uploaded to <b>your own backend server</b> (this computer when run locally). Speech-to-text and face/head analysis run locally on that server.</li>
          <li>Only the <b>transcript text and your profile/interview context</b> are sent to the external AI provider configured in the backend (Gemini or OpenAI-compatible) to generate and evaluate questions. Video and audio files are not sent to it.</li>
          <li>You can delete any recording, or all your data, from History or Settings. Recordings are auto-deleted after the configured retention period.</li>
          <li>Visual metrics are coaching feedback only and do not judge emotion, honesty or personality.</li>
        </ul>
        <label className="check"><input type="checkbox" checked={f.consent} onChange={set('consent')} /> I consent to recording and analysis of my webcam video and microphone audio. (Untick to use text-only answers.)</label>
      </div>
      {err && <div className="error">{err}</div>}
      <button className="btn" disabled={busy}>{busy ? 'Generating first question…' : 'Continue to device check'}</button>
    </form>
  )
}
