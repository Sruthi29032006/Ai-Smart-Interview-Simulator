import React from 'react'

export const LABELS = { technical: 'Technical knowledge', relevance: 'Answer relevance', communication: 'Communication',
  speaking: 'Speaking delivery', visual: 'Visual interview behavior', coding: 'Coding performance' }

export function Bar({ label, value, max = 100, note }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100))
  const col = pct >= 70 ? 'var(--good)' : pct >= 45 ? 'var(--mid)' : 'var(--bad)'
  return (
    <div className="bar">
      <div className="barhead"><span>{label}</span><b>{value == null ? 'not measured' : Math.round(value * 10) / 10}</b></div>
      <div className="track"><div style={{ width: `${pct}%`, background: value == null ? 'transparent' : col }} /></div>
      {note && <div className="small muted">{note}</div>}
    </div>
  )
}

const List = ({ title, items, cls }) => items?.length ? <div className={`list ${cls || ''}`}><h5>{title}</h5><ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul></div> : null

export function AudioBlock({ a }) {
  if (!a) return null
  if (!a.available) return <div className="box"><h5>🎙 Speech delivery</h5><p className="muted small">{a.reason || 'Not available'}</p></div>
  return (
    <div className="box">
      <h5>🎙 Speech delivery · {a.delivery_score}/100</h5>
      <div className="stats">
        <span><b>{a.words_per_minute}</b> words/min</span><span><b>{a.word_count}</b> words</span>
        <span><b>{a.hesitation_fillers}</b> um/uh</span><span><b>{a.long_pauses.length}</b> long pauses</span>
        <span><b>{a.repeated_words}</b> repeats</span><span><b>{a.speaking_time_sec}s</b> speaking</span>
      </div>
      {Object.keys(a.filler_counts || {}).length > 0 && <p className="small">Filler words: {Object.entries(a.filler_counts).map(([k, v]) => `${k} ×${v}`).join(', ')}</p>}
      <ul className="small">{a.feedback.map((f, i) => <li key={i}>{f}</li>)}</ul>
      <p className="small muted">{a.notes}</p>
    </div>
  )
}

export function VisualBlock({ v }) {
  if (!v) return null
  if (!v.available) return <div className="box"><h5>👁 Visual behavior</h5><p className="muted small">{v.reason || 'Not available'}</p></div>
  return (
    <div className="box">
      <h5>👁 Visual behavior · {v.visual_score}/100 <span className="tag">{v.mode === 'mediapipe_face_landmarker' ? 'MediaPipe landmarks' : 'basic face detection only'}</span></h5>
      <div className="stats">
        <span><b>{v.face_visible_pct}%</b> face visible</span>
        {v.looking_at_camera_pct != null && <span><b>{v.looking_at_camera_pct}%</b> facing camera</span>}
        {v.head_movement_deg != null && <span><b>{v.head_movement_deg}°</b> head movement</span>}
        <span>lighting: <b>{v.lighting}</b></span><span>distance: <b>{v.distance}</b></span><span><b>{v.frames_analyzed}</b> frames</span>
      </div>
      <ul className="small">{v.feedback.map((f, i) => <li key={i}>{f}</li>)}</ul>
      {v.expression && <p className="small muted">Facial movement (uncertain estimate, not scored): smile ≈ {v.expression.smile_mean}, variation ≈ {v.expression.facial_movement_variation}. {v.expression.note}</p>}
      {v.gaze_note && <p className="small muted">{v.gaze_note}</p>}
      <p className="small muted">{v.limitations}</p>
    </div>
  )
}

export function AnswerFeedback({ q }) {
  const a = q.answer; const ev = a?.evaluation
  if (!ev) return null
  const dims = ['technical', 'relevance', 'completeness', 'clarity', 'structure', 'communication', 'examples']
  return (
    <div className="feedback">
      <div className="scorebig">{a.score}<small>/100</small></div>
      <div className="grid2">{dims.map((d) => <Bar key={d} label={d[0].toUpperCase() + d.slice(1)} value={ev[d]} max={10} />)}</div>
      {ev.coding && <div className="box"><h5>💻 Coding evaluation</h5>
        <div className="grid2">{['correctness', 'logic', 'edge_cases', 'complexity', 'code_quality'].map((d) => <Bar key={d} label={d.replace('_', ' ')} value={ev.coding[d]} max={10} />)}</div>
        <p className="small">{ev.coding.notes}</p><p className="small muted">Code is judged by the AI; it is not executed.</p></div>}
      <List title="✅ Correct concepts" items={ev.correct_concepts} cls="good" />
      <List title="➖ Missing concepts" items={ev.missing_concepts} cls="mid" />
      <List title="❌ Incorrect statements" items={ev.incorrect_statements} cls="bad" />
      <List title="💡 Suggestions" items={ev.suggestions} />
      <div className="box"><h5>Reference answer</h5><p>{ev.reference_answer}</p><p className="small muted">{ev.explanation}</p></div>
      <AudioBlock a={a.audio_analysis} /><VisualBlock v={a.visual_analysis} />
    </div>
  )
}
