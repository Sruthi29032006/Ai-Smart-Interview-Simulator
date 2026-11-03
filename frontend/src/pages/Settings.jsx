import React, { useState } from 'react'
import { api } from '../api.js'

export default function Settings() {
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  const run = async (fn, confirmText) => { if (!confirm(confirmText)) return; setErr(''); try { setMsg(await fn()) } catch (e) { setErr(e.message) } }
  return (
    <div>
      <h2>Settings &amp; privacy</h2>
      <div className="card">
        <h3>How your data is handled</h3>
        <ul>
          <li>Webcam/microphone are recorded only during an answer, with a visible REC indicator, and only if you gave consent when configuring the interview.</li>
          <li>Recordings are stored on the server running this app (your computer if run locally) and are visible only to you. Administrators see aggregate statistics only.</li>
          <li>Speech-to-text and face/head analysis run locally on the server. Only transcript text and interview context are sent to the configured external LLM provider.</li>
          <li>Recordings are automatically deleted after the retention period configured by the server owner (default 30 days).</li>
        </ul>
      </div>
      <div className="card">
        <h3>Delete my data</h3>
        <div className="row wrap">
          <button className="btn secondary" onClick={() => run(async () => `Deleted ${(await api('/me/recordings', { method: 'DELETE' })).deleted} recording(s).`, 'Delete ALL your stored recordings? Transcripts and reports are kept.')}>Delete all my recordings</button>
          <button className="btn danger" onClick={() => run(async () => (await api('/interviews', { method: 'DELETE' })).detail, 'Delete ALL interviews, transcripts, reports and recordings permanently?')}>Delete all interviews &amp; data</button>
        </div>
        {msg && <div className="ok">{msg}</div>}{err && <div className="error">{err}</div>}
      </div>
    </div>
  )
}
