import { createContext, useContext, useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  BarChart3, BrainCircuit, Database, FileUp, Info, LayoutDashboard, Menu, MessageSquareText, RefreshCw, Table2, Warehouse,
} from 'lucide-react'
import { api, API_URL } from '../api'
import { Alert } from './ui'

const NAV = [
  ['Analyse', [
    ['/', 'Dashboard', LayoutDashboard],
    ['/analyzer', 'Sentiment Analyzer', MessageSquareText],
    ['/reviews', 'Reviews Explorer', Table2],
    ['/insights', 'Insights & Analytics', BarChart3],
  ]],
  ['Data & Models', [
    ['/datasets', 'Dataset Management', FileUp],
    ['/models', 'Model Performance', BrainCircuit],
    ['/warehouse', 'Data Warehouse', Warehouse],
  ]],
  ['Project', [['/about', 'About Project', Info]]],
]

const HealthContext = createContext({ health: null, refresh: () => {} })
export const useHealth = () => useContext(HealthContext)

export default function Layout({ children }) {
  const [open, setOpen] = useState(false)
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState(null)
  const location = useLocation()

  const refresh = () => api.health().then((h) => { setHealth(h); setHealthError(null) }).catch(setHealthError)
  useEffect(() => { refresh() }, [location.pathname])
  useEffect(() => setOpen(false), [location.pathname])

  const mode = health?.storage?.mode
  const dot = healthError ? 'var(--err)' : mode === 'mongodb' ? 'var(--ok)' : mode === 'memory' ? 'var(--warn)' : 'var(--err)'
  const title = NAV.flatMap((s) => s[1]).find(([p]) => p === location.pathname)?.[1] || 'ReviewIQ'

  return (
    <HealthContext.Provider value={{ health, refresh }}>
      <div className="app">
        <aside className={`sidebar ${open ? 'open' : ''}`}>
          <div className="brand">
            <div className="brand-mark"><BrainCircuit size={20} color="#fff" /></div>
            <div><div className="brand-name">ReviewIQ</div><div className="brand-sub">Sentiment · Warehouse · OLAP</div></div>
          </div>
          <nav className="nav">
            {NAV.map(([section, items]) => (
              <div key={section} style={{ display: 'contents' }}>
                <div className="nav-section">{section}</div>
                {items.map(([to, label, Icon]) => (
                  <NavLink key={to} to={to} end={to === '/'}><Icon size={17} /> {label}</NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="sidebar-foot">
            <div><span className="status-dot" style={{ background: dot }} />
              {healthError ? 'Backend offline' : mode === 'mongodb' ? 'MongoDB connected' : mode === 'memory' ? 'Demo store (in-memory)' : mode ? 'Database unavailable' : 'Checking…'}
            </div>
            <div style={{ marginTop: 4 }}>
              <span className="status-dot" style={{ background: health?.models?.ready ? 'var(--ok)' : 'var(--unl)' }} />
              {health?.models?.ready ? 'Models loaded' : 'Models not trained'}
            </div>
            <a href={`${API_URL}/docs`} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: 8, color: '#a5b4fc' }}>API docs (Swagger) ↗</a>
          </div>
        </aside>

        <div className="main">
          <header className="topbar">
            <div className="row">
              <button className="btn sm ghost menu-btn" onClick={() => setOpen(!open)} aria-label="Menu"><Menu size={18} /></button>
              <strong>{title}</strong>
            </div>
            <span className="small muted mono hide-sm">{API_URL}</span>
          </header>
          <main className="content">
            {healthError && (
              <div style={{ marginBottom: 16 }}>
                <Alert kind="err" title="Backend not reachable.">
                  {healthError.message} <button className="btn sm" onClick={refresh} style={{ marginLeft: 8 }}><RefreshCw size={13} /> Retry</button>
                </Alert>
              </div>
            )}
            {mode === 'memory' && (
              <div style={{ marginBottom: 16 }}>
                <Alert kind="warn" title="Demo mode.">
                  {health.storage.description} Start MongoDB (or set <span className="mono">MONGO_URI</span> in <span className="mono">backend/.env</span>) and{' '}
                  <button className="btn sm" onClick={() => api.reconnect().then(refresh)}><Database size={13} /> Reconnect</button>
                </Alert>
              </div>
            )}
            {mode === 'unavailable' && (
              <div style={{ marginBottom: 16 }}>
                <Alert kind="err" title="MongoDB unavailable.">{health.storage.description}</Alert>
              </div>
            )}
            {children}
          </main>
        </div>
      </div>
    </HealthContext.Provider>
  )
}
