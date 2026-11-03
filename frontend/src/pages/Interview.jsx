import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { AnswerFeedback } from '../components.jsx'

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`
const pickMime = () => ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'].find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || ''
const mediaError = (e) => ({
  NotAllowedError: 'Permission denied. Click the camera/lock icon in the address bar, set Camera and Microphone to Allow, then press Retry.',
  NotFoundError: 'No camera or microphone was found. Connect one and press Retry, or use text answers.',
  NotReadableError: 'The camera/microphone is in use by another application (Teams, Zoom…). Close it and press Retry.',
  OverconstrainedError: 'The selected device is unavailable. Choose another device.',
}[e.name] || `Could not access camera/microphone: ${e.message}`)

export default function Interview() {
  const { id } = useParams(); const nav = useNavigate()
  const [iv, setIv] = useState(null); const [q, setQ] = useState(null)
  const [phase, setPhase] = useState('devices') // devices|ready|recording|review|processing|transcript|evaluating|feedback
  const [textMode, setTextMode] = useState(false)
  const [err, setErr] = useState(''); const [camErr, setCamErr] = useState(''); const [warn, setWarn] = useState('')
  const [cams, setCams] = useState([]); const [mics, setMics] = useState([]); const [camId, setCamId] = useState(''); const [micId, setMicId] = useState('')
  const [camOn, setCamOn] = useState(true); const [micOn, setMicOn] = useState(true); const [level, setLevel] = useState(0)
  const [secs, setSecs] = useState(0); const [paused, setPaused] = useState(false); const [elapsed, setElapsed] = useState(0)
  const [blob, setBlob] = useState(null); const [blobUrl, setBlobUrl] = useState('')
  const [transcript, setTranscript] = useState(''); const [feedbackQ, setFeedbackQ] = useState(null)
  const [online, setOnline] = useState(navigator.onLine); const [backendOk, setBackendOk] = useState(true)
  const [confirmEnd, setConfirmEnd] = useState(false); const [showHint, setShowHint] = useState(false); const [busy, setBusy] = useState(false)
  const [streamVer, setStreamVer] = useState(0)
  const stream = useRef(null); const video = useRef(null); const rec = useRef(null); const chunks = useRef([]); const audioCtx = useRef(null)

  const stopMedia = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop()); stream.current = null
    audioCtx.current?.close().catch(() => {}); audioCtx.current = null
  }, [])

  const startMedia = useCallback(async (cam, mic) => {
    stopMedia(); setCamErr('')
    if (!navigator.mediaDevices?.getUserMedia) { setCamErr('This browser cannot access the camera. Use Chrome/Edge on http://localhost:5173 or HTTPS.'); return }
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: cam ? { deviceId: { exact: cam } } : { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: mic ? { deviceId: { exact: mic }, echoCancellation: true, noiseSuppression: true } : { echoCancellation: true, noiseSuppression: true } })
      stream.current = s; setCamOn(true); setMicOn(true); setStreamVer((v) => v + 1)
      const list = await navigator.mediaDevices.enumerateDevices()
      setCams(list.filter((d) => d.kind === 'videoinput')); setMics(list.filter((d) => d.kind === 'audioinput'))
      setCamId(s.getVideoTracks()[0]?.getSettings().deviceId || ''); setMicId(s.getAudioTracks()[0]?.getSettings().deviceId || '')
      const ctx = new (window.AudioContext || window.webkitAudioContext)(); audioCtx.current = ctx
      const an = ctx.createAnalyser(); an.fftSize = 512; ctx.createMediaStreamSource(s).connect(an)
      const buf = new Uint8Array(an.fftSize)
      const tick = setInterval(() => { if (!audioCtx.current) return clearInterval(tick)
        an.getByteTimeDomainData(buf); let m = 0; for (const v of buf) m = Math.max(m, Math.abs(v - 128)); setLevel(Math.min(100, m * 1.6)) }, 100)
    } catch (e) { setCamErr(mediaError(e)) }
  }, [stopMedia])

  // load interview + resume state
  useEffect(() => {
    api(`/interviews/${id}`).then((d) => {
      if (d.status !== 'active') return nav(`/report/${id}`, { replace: true })
      setIv(d)
      const last = d.questions[d.questions.length - 1]
      setQ(last)
      if (last.answer?.status === 'evaluated') { setFeedbackQ(last); setPhase('feedback') }
      else if (last.answer?.status === 'transcribed') { setTranscript(last.answer.transcript); setPhase('transcript') }
      if (!d.consent_recording) setTextMode(true)
    }).catch((e) => setErr(e.message))
    startMedia()
    return stopMedia
  }, [id])

  useEffect(() => { if (video.current && stream.current) video.current.srcObject = stream.current }, [streamVer, phase])
  useEffect(() => { const t = setInterval(() => iv && setElapsed((Date.now() - new Date(iv.started_at + 'Z')) / 1000), 1000); return () => clearInterval(t) }, [iv])
  useEffect(() => { if (phase !== 'recording' || paused) return; const t = setInterval(() => setSecs((s) => s + 1), 1000); return () => clearInterval(t) }, [phase, paused])
  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false)
    window.addEventListener('online', on); window.addEventListener('offline', off)
    const t = setInterval(() => fetch('/api/health').then((r) => setBackendOk(r.ok)).catch(() => setBackendOk(false)), 10000)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); clearInterval(t) }
  }, [])

  const toggleTrack = (kind, on, set) => { stream.current?.[kind === 'video' ? 'getVideoTracks' : 'getAudioTracks']().forEach((t) => (t.enabled = !on)); set(!on) }

  const startRec = () => {
    if (!stream.current) return setErr('Camera/microphone not available. Press Retry in the device panel.')
    setErr(''); chunks.current = []
    const mime = pickMime()
    const mr = new MediaRecorder(stream.current, mime ? { mimeType: mime, videoBitsPerSecond: 1500000 } : undefined)
    mr.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    mr.onstop = () => { const b = new Blob(chunks.current, { type: 'video/webm' }); setBlob(b); setBlobUrl(URL.createObjectURL(b)); setPhase('review') }
    mr.start(1000); rec.current = mr; setSecs(0); setPaused(false); setPhase('recording')
  }
  const stopRec = () => { rec.current?.state !== 'inactive' && rec.current?.stop() }
  const pauseRec = () => { if (paused) { rec.current.resume(); setPaused(false) } else { rec.current.pause(); setPaused(true) } }
  const reRecord = () => { URL.revokeObjectURL(blobUrl); setBlob(null); setBlobUrl(''); setPhase('ready') }

  const processRec = async () => {
    setPhase('processing'); setErr(''); setWarn('')
    try {
      const fd = new FormData(); fd.append('file', blob, 'answer.webm')
      const a = await api(`/interviews/${id}/questions/${q.id}/media`, { method: 'POST', form: fd })
      setTranscript(a.transcript); setWarn(a.warning || ''); setPhase('transcript')
    } catch (e) { setErr(e.message); setPhase('review') }
  }

  const submit = async () => {
    setPhase('evaluating'); setErr('')
    try {
      const r = await api(`/interviews/${id}/questions/${q.id}/submit`, { method: 'POST', body: { transcript, mode: textMode && !blob ? 'text' : 'voice' } })
      setFeedbackQ(r.question); setPhase('feedback')
    } catch (e) { setErr(e.message); setPhase('transcript') }
  }

  const finish = async () => {
    setBusy(true); setErr('')
    try {
      stopMedia()
      const answered = iv.questions.some((x) => x.answer?.status === 'evaluated') || feedbackQ
      await api(`/interviews/${id}/${answered ? 'finish' : 'abandon'}`, { method: 'POST' })
      nav(answered ? `/report/${id}` : '/history')
    } catch (e) { setErr(e.message); setBusy(false); setConfirmEnd(false) }
  }

  const next = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api(`/interviews/${id}/next`, { method: 'POST' })
      if (r.done) return finish()
      setIv({ ...iv, questions: [...iv.questions.filter((x) => x.id !== feedbackQ.id), feedbackQ, r.question] })
      setQ(r.question); setFeedbackQ(null); setBlob(null); setBlobUrl(''); setTranscript(''); setWarn(''); setShowHint(false); setSecs(0); setPhase('ready')
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (!iv || !q) return <div className="center">{err || 'Loading interview…'}</div>
  const total = iv.num_questions
  const answeredCount = iv.questions.filter((x) => x.answer?.status === 'evaluated').length + (feedbackQ && !iv.questions.find((x) => x.id === feedbackQ.id && x.answer?.status === 'evaluated') ? 1 : 0)
  const isLast = total > 0 && q.number >= total
  const rtime = phase === 'recording'

  const devStatus = (ok, label) => <span className={`dot ${ok ? 'on' : 'off'}`}>{label}</span>
  const trackLive = (k) => stream.current?.[k === 'v' ? 'getVideoTracks' : 'getAudioTracks']()[0]?.readyState === 'live'

  return (
    <div className="interview">
      <div className="topbar">
        <b>{iv.type}</b><span>⏱ {fmt(elapsed)}</span>
        <span>{devStatus(online && backendOk, online ? (backendOk ? 'Online' : 'Server unreachable') : 'Offline')}</span>
        <span>{devStatus(trackLive('v') && camOn, 'Camera')}</span><span>{devStatus(trackLive('a') && micOn, 'Mic')}</span>
        <button className="btn danger small" onClick={() => setConfirmEnd(true)}>End interview</button>
      </div>

      <div className="split">
        <section className="left">
          <div className="videobox">
            {phase === 'review' && blobUrl
              ? <video key="pb" src={blobUrl} controls playsInline />
              : <video key="live" ref={video} autoPlay muted playsInline className="mirror" />}
            {(!stream.current || camErr) && phase !== 'review' && <div className="novideo">{camErr || 'Camera off'}</div>}
            {!camOn && !camErr && phase !== 'review' && <div className="novideo">Camera is turned off</div>}
            {rtime && <div className="rec"><i />{paused ? 'PAUSED' : 'REC'} {fmt(secs)}</div>}
          </div>
          <div className="meter"><div style={{ width: `${micOn ? level : 0}%` }} /></div>
          <div className="row wrap">
            <button className="btn secondary small" onClick={() => toggleTrack('video', camOn, setCamOn)}>{camOn ? '📷 Camera on' : '🚫 Camera off'}</button>
            <button className="btn secondary small" onClick={() => toggleTrack('audio', micOn, setMicOn)}>{micOn ? '🎤 Mic on' : '🔇 Mic muted'}</button>
            <button className="btn secondary small" onClick={() => startMedia(camId, micId)} disabled={rtime}>↻ Retry devices</button>
          </div>
          <div className="grid2">
            <label className="small">Camera<select disabled={rtime} value={camId} onChange={(e) => { setCamId(e.target.value); startMedia(e.target.value, micId) }}>{cams.map((d, i) => <option key={d.deviceId} value={d.deviceId}>{d.label || `Camera ${i + 1}`}</option>)}</select></label>
            <label className="small">Microphone<select disabled={rtime} value={micId} onChange={(e) => { setMicId(e.target.value); startMedia(camId, e.target.value) }}>{mics.map((d, i) => <option key={d.deviceId} value={d.deviceId}>{d.label || `Microphone ${i + 1}`}</option>)}</select></label>
          </div>
          {camErr && <div className="error">{camErr}</div>}
          {!micOn && rtime && <div className="warn">Your microphone is muted: nothing is being recorded.</div>}
          {phase === 'devices' && <p className="small muted">Speak and check the green bar moves. Make sure your face is centred and well lit.</p>}
        </section>

        <section className="right">
          <div className="qcard">
            <div className="chips"><span className="chip">Question {q.number}{total ? ` / ${total}` : ''}</span><span className="chip">{q.category}</span>
              <span className={`chip d-${q.difficulty}`}>{q.difficulty}</span>{q.is_followup && <span className="chip">Follow-up</span>}</div>
            {total > 0 && <div className="track"><div style={{ width: `${(answeredCount / total) * 100}%`, background: 'var(--accent)' }} /></div>}
            <p className="qtext">{q.text}</p>
            {q.hint && phase !== 'feedback' && (showHint ? <p className="small muted">💡 {q.hint}</p> : <button className="link small" onClick={() => setShowHint(true)}>Show hint</button>)}
          </div>

          {err && <div className="error">{err} {phase === 'transcript' && <button className="link" onClick={submit}>Retry</button>}</div>}

          {phase === 'devices' && (
            <div className="panel"><h4>Step 1 · Device check</h4>
              <p className="small">Confirm your camera preview and microphone level, then begin. Take a moment to read the question first.</p>
              <div className="row wrap">
                <button className="btn" disabled={!stream.current && !textMode} onClick={() => setPhase('ready')}>Devices look good, begin</button>
                <button className="btn secondary" onClick={() => { setTextMode(true); setPhase('ready') }}>Use text answers instead</button>
              </div>
            </div>)}

          {phase === 'ready' && (
            <div className="panel"><h4>Your answer</h4>
              {!textMode ? (<>
                <p className="small">Read the question, then press Start recording and answer out loud while looking at the camera. Aim for 1–2 minutes.</p>
                <div className="row wrap">
                  <button className="btn rec-btn" onClick={startRec} disabled={!iv.consent_recording || !stream.current}>● Start recording</button>
                  <button className="btn secondary" onClick={() => { setTextMode(true) }}>Type instead</button>
                </div>
                {!iv.consent_recording && <p className="warn">Recording consent was not given for this interview, so only text answers are possible.</p>}
              </>) : (<>
                <textarea className={q.is_coding ? 'code' : ''} rows={q.is_coding ? 14 : 8} value={transcript} onChange={(e) => setTranscript(e.target.value)}
                  placeholder={q.is_coding ? 'Write your solution and explain your approach and complexity…' : 'Type your answer…'} />
                <div className="row wrap"><button className="btn" onClick={submit} disabled={transcript.trim().split(/\s+/).length < 3}>Submit answer</button>
                  {iv.consent_recording && <button className="btn secondary" onClick={() => setTextMode(false)}>Switch to voice</button>}</div>
              </>)}
            </div>)}

          {phase === 'recording' && (
            <div className="panel"><h4>Recording… speak your answer</h4>
              <div className="row wrap"><button className="btn secondary" onClick={pauseRec}>{paused ? '▶ Resume' : '⏸ Pause'}</button>
                <button className="btn danger" onClick={stopRec}>■ Stop recording</button></div>
              <p className="small muted">Recording is stored on your server only after you press Submit and process it.</p></div>)}

          {phase === 'review' && (
            <div className="panel"><h4>Review your recording</h4>
              <p className="small">Play it back on the left. Process it to get the transcript, or record again.</p>
              <div className="row wrap"><button className="btn" onClick={processRec}>Process recording</button><button className="btn secondary" onClick={reRecord}>Record again</button></div></div>)}

          {phase === 'processing' && <div className="panel"><div className="spinner" /> Uploading, transcribing speech, analysing audio and video… (the first run may take a while while models load)</div>}

          {phase === 'transcript' && (
            <div className="panel"><h4>Your transcript</h4>
              {warn && <div className="warn">{warn}</div>}
              <p className="small muted">{blob || q.answer?.has_media ? 'Produced by speech-to-text. Correct any mistakes before submitting. Your edited text is what the AI evaluates.' : 'Your typed answer.'}</p>
              <textarea rows={8} value={transcript} onChange={(e) => setTranscript(e.target.value)} />
              <div className="row wrap"><button className="btn" onClick={submit} disabled={transcript.trim().split(/\s+/).length < 3}>Submit for evaluation</button>
                {(blob || !textMode) && <button className="btn secondary" onClick={() => { setPhase('ready'); setTranscript('') }}>Re-record</button>}</div></div>)}

          {phase === 'evaluating' && <div className="panel"><div className="spinner" /> AI is evaluating your answer…</div>}

          {phase === 'feedback' && feedbackQ && (
            <div className="panel"><h4>Feedback</h4><AnswerFeedback q={feedbackQ} />
              <div className="row"><button className="btn" onClick={next} disabled={busy}>{busy ? 'Please wait…' : isLast ? 'Finish & generate report' : 'Next question →'}</button>
                {total === 0 && <button className="btn secondary" onClick={finish} disabled={busy}>Finish & generate report</button>}</div></div>)}
        </section>
      </div>

      {confirmEnd && (
        <div className="modal"><div className="card">
          <h3>End this interview?</h3>
          <p>{answeredCount > 0 ? `Your ${answeredCount} answered question(s) will be scored and a report generated. Unanswered questions are excluded.` : 'You have not completed any answer, so this interview will be saved as abandoned.'}</p>
          {err && <div className="error">{err}</div>}
          <div className="row"><button className="btn danger" onClick={finish} disabled={busy}>{busy ? 'Working…' : 'Yes, end interview'}</button>
            <button className="btn secondary" onClick={() => setConfirmEnd(false)}>Continue interview</button></div>
        </div></div>)}
    </div>
  )
}
