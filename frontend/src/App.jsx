import React, { createContext, useContext, useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { api, tok } from './api.js'
import Landing from './pages/Landing.jsx'
import { Login, Register, Forgot, Reset } from './pages/Auth.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Profile from './pages/Profile.jsx'
import Setup from './pages/Setup.jsx'
import Interview from './pages/Interview.jsx'
import History from './pages/History.jsx'
import Report from './pages/Report.jsx'
import Settings from './pages/Settings.jsx'
import Admin from './pages/Admin.jsx'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

function Protected({ children, admin }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="center">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (admin && user.role !== 'admin') return <Navigate to="/dashboard" replace />
  return children
}

function Nav() {
  const { user, logout } = useAuth()
  return (
    <header className="nav">
      <Link to="/" className="brand">🎯 AI Interview Simulator</Link>
      {user ? (
        <nav>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/setup">New Interview</NavLink>
          <NavLink to="/history">History</NavLink>
          <NavLink to="/profile">Profile</NavLink>
          <NavLink to="/settings">Settings</NavLink>
          {user.role === 'admin' && <NavLink to="/admin">Admin</NavLink>}
          <button className="link" onClick={logout}>Logout ({user.full_name.split(' ')[0]})</button>
        </nav>
      ) : (
        <nav><NavLink to="/login">Login</NavLink><NavLink to="/register">Register</NavLink></nav>
      )}
    </header>
  )
}

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!tok.get())
  const nav = useNavigate()
  useEffect(() => {
    if (!tok.get()) return
    api('/auth/me').then(setUser).catch(() => tok.clear()).finally(() => setLoading(false))
  }, [])
  const login = (r) => { tok.set(r.token); setUser(r.user) }
  const logout = () => { tok.clear(); setUser(null); nav('/') }
  const P = (el, admin) => <Protected admin={admin}>{el}</Protected>
  return (
    <Ctx.Provider value={{ user, setUser, loading, login, logout }}>
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot" element={<Forgot />} />
          <Route path="/reset" element={<Reset />} />
          <Route path="/dashboard" element={P(<Dashboard />)} />
          <Route path="/profile" element={P(<Profile />)} />
          <Route path="/setup" element={P(<Setup />)} />
          <Route path="/interview/:id" element={P(<Interview />)} />
          <Route path="/history" element={P(<History />)} />
          <Route path="/report/:id" element={P(<Report />)} />
          <Route path="/settings" element={P(<Settings />)} />
          <Route path="/admin" element={P(<Admin />, true)} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </Ctx.Provider>
  )
}
