import React, { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../App.jsx'

function useForm(initial) {
  const [v, setV] = useState(initial)
  return [v, (k) => (e) => setV({ ...v, [k]: e.target.value })]
}

export function Login() {
  const [f, set] = useForm({ email: '', password: '' })
  const [err, setErr] = useState(''); const { login } = useAuth(); const nav = useNavigate()
  const submit = async (e) => { e.preventDefault(); setErr('')
    try { login(await api('/auth/login', { method: 'POST', body: f })); nav('/dashboard') } catch (x) { setErr(x.message) } }
  return (
    <form className="card narrow" onSubmit={submit}>
      <h2>Login</h2>
      <label>Email<input type="email" required value={f.email} onChange={set('email')} /></label>
      <label>Password<input type="password" required value={f.password} onChange={set('password')} /></label>
      {err && <div className="error">{err}</div>}
      <button className="btn">Login</button>
      <p className="small"><Link to="/forgot">Forgot password?</Link> · <Link to="/register">Create account</Link></p>
    </form>
  )
}

export function Register() {
  const [f, set] = useForm({ full_name: '', email: '', password: '' })
  const [err, setErr] = useState(''); const { login } = useAuth(); const nav = useNavigate()
  const submit = async (e) => { e.preventDefault(); setErr('')
    try { login(await api('/auth/register', { method: 'POST', body: f })); nav('/profile') } catch (x) { setErr(x.message) } }
  return (
    <form className="card narrow" onSubmit={submit}>
      <h2>Create account</h2>
      <label>Full name<input required minLength={2} value={f.full_name} onChange={set('full_name')} /></label>
      <label>Email<input type="email" required value={f.email} onChange={set('email')} /></label>
      <label>Password (min 8 characters)<input type="password" required minLength={8} value={f.password} onChange={set('password')} /></label>
      {err && <div className="error">{err}</div>}
      <button className="btn">Register</button>
      <p className="small">Already registered? <Link to="/login">Login</Link></p>
    </form>
  )
}

export function Forgot() {
  const [email, setEmail] = useState(''); const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  const submit = async (e) => { e.preventDefault(); setErr('')
    try { setMsg((await api('/auth/forgot', { method: 'POST', body: { email } })).detail) } catch (x) { setErr(x.message) } }
  return (
    <form className="card narrow" onSubmit={submit}>
      <h2>Forgot password</h2>
      <p className="small muted">This local setup has no email server. The reset link is printed in the backend terminal window.</p>
      <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      {err && <div className="error">{err}</div>}{msg && <div className="ok">{msg}</div>}
      <button className="btn">Get reset link</button>
    </form>
  )
}

export function Reset() {
  const [q] = useSearchParams(); const [pw, setPw] = useState(''); const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  const submit = async (e) => { e.preventDefault(); setErr('')
    try { await api('/auth/reset', { method: 'POST', body: { token: q.get('token'), password: pw } }); setMsg('Password updated. You can log in now.') } catch (x) { setErr(x.message) } }
  return (
    <form className="card narrow" onSubmit={submit}>
      <h2>Reset password</h2>
      <label>New password<input type="password" minLength={8} required value={pw} onChange={(e) => setPw(e.target.value)} /></label>
      {err && <div className="error">{err}</div>}{msg && <div className="ok">{msg} <Link to="/login">Login</Link></div>}
      <button className="btn">Update password</button>
    </form>
  )
}
