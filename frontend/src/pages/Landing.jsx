import React from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../App.jsx'

export default function Landing() {
  const { user } = useAuth()
  return (
    <div className="hero">
      <h1>Practice real video interviews with an AI interviewer</h1>
      <p>Answer out loud on your webcam. Get your speech transcribed, your delivery analysed, your face framing and head movement reviewed, and every answer evaluated by AI, with a full performance report.</p>
      <div className="row center-row">
        {user ? <Link className="btn" to="/setup">Start an interview</Link> : <><Link className="btn" to="/register">Get started</Link><Link className="btn secondary" to="/login">Login</Link></>}
      </div>
      <div className="grid3">
        <div className="card"><h3>🎥 Webcam + mic capture</h3><p>Real recording in your browser with a live preview, device selection and a visible recording indicator.</p></div>
        <div className="card"><h3>🧠 AI questions &amp; evaluation</h3><p>Questions are generated for your role and adapt to your answers, with follow-ups and concept-level feedback.</p></div>
        <div className="card"><h3>📊 Analytics</h3><p>Technical, communication, speaking and visual-behavior trends across all of your interviews.</p></div>
      </div>
      <p className="muted small">Visual and speech metrics are coaching feedback only. They do not measure emotion, honesty, personality or suitability for a job.</p>
    </div>
  )
}
