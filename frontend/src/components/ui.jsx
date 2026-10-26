import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'

export const SENT_COLORS = { positive: '#1f9e74', neutral: '#d49a12', negative: '#dc4c64', unlabeled: '#9aa3af' }
export const SENTIMENTS = ['positive', 'neutral', 'negative']
export const MODEL_COLORS = { logistic_regression: '#4f46e5', naive_bayes: '#0ea5a4' }

export const fmt = {
  int: (n) => (n == null ? '—' : Number(n).toLocaleString()),
  pct: (n, d = 1) => (n == null ? '—' : `${Number(n).toFixed(d)}%`),
  ratio: (n, d = 1) => (n == null ? '—' : `${(Number(n) * 100).toFixed(d)}%`),
  num: (n, d = 2) => (n == null ? '—' : Number(n).toFixed(d)),
  date: (s) => (s ? new Date(s).toLocaleString() : '—'),
}

/** Load async data with loading / error / reload state. */
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const seq = useRef(0)
  const run = useCallback(() => {
    const id = ++seq.current
    setState((s) => ({ ...s, loading: true, error: null }))
    return fn()
      .then((data) => id === seq.current && setState({ data, error: null, loading: false }))
      .catch((error) => id === seq.current && setState((s) => ({ data: s.data, error, loading: false })))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { run() }, [run])
  return { ...state, reload: run }
}

export function Card({ title, sub, actions, children, className = '', bodyClass = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <h3>{title} {sub && <span className="sub">· {sub}</span>}</h3>
          {actions && <div className="row">{actions}</div>}
        </div>
      )}
      <div className={`card-body ${bodyClass}`}>{children}</div>
    </section>
  )
}

export function Stat({ label, value, note, icon: Icon, color }) {
  return (
    <div className="card stat">
      <div className="stat-label">{Icon && <Icon size={15} color={color || 'var(--muted)'} />} {label}</div>
      <div className="stat-value" style={color ? { color } : undefined}>{value}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  )
}

export function Pill({ value, kind }) {
  const k = kind || value || 'unlabeled'
  return <span className={`pill ${k}`}>{value || 'unlabeled'}</span>
}

const ICONS = { info: Info, warn: AlertTriangle, err: XCircle, ok: CheckCircle2 }
export function Alert({ kind = 'info', title, children }) {
  const Icon = ICONS[kind]
  return (
    <div className={`alert ${kind}`} role={kind === 'err' ? 'alert' : undefined}>
      <Icon size={17} />
      <div>{title && <strong>{title} </strong>}{children}</div>
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null
  return (
    <Alert kind="err" title="Something went wrong.">
      {error.message || String(error)}
      {onRetry && <> <button className="btn sm" style={{ marginLeft: 8 }} onClick={onRetry}>Retry</button></>}
    </Alert>
  )
}

export function Loading({ text = 'Loading…' }) {
  return <div className="loading"><div className="spinner" /> {text}</div>
}

export function Empty({ title, children, action }) {
  return (
    <div className="empty">
      <h4>{title}</h4>
      <div>{children}</div>
      {action && <div className="mt">{action}</div>}
    </div>
  )
}

export function ProbBar({ label, value, color }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div className="row between small"><span style={{ textTransform: 'capitalize' }}>{label}</span><strong>{fmt.ratio(value)}</strong></div>
      <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.max(0, value * 100)}%`, background: color }} /></div>
    </div>
  )
}

export function Seg({ options, value, onChange }) {
  return (
    <div className="seg">
      {options.map((o) => {
        const [v, l] = Array.isArray(o) ? o : [o, o]
        return <button key={v} type="button" className={value === v ? 'on' : ''} onClick={() => onChange(v)}>{l}</button>
      })}
    </div>
  )
}

export function Stars({ value }) {
  if (value == null) return <span className="muted">—</span>
  const n = Math.round(value)
  return <span title={`${value} / 5`} style={{ color: '#e0a100', letterSpacing: 1, whiteSpace: 'nowrap' }}>{'★'.repeat(n)}<span style={{ color: '#d6d9df' }}>{'★'.repeat(Math.max(0, 5 - n))}</span></span>
}

export const tooltipStyle = { borderRadius: 8, border: '1px solid #e3e6ec', fontSize: 12.5, boxShadow: '0 4px 16px rgba(16,20,42,.08)' }
