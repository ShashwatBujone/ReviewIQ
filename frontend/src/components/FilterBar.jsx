import { useEffect, useState } from 'react'
import { RotateCcw, Search } from 'lucide-react'
import { api } from '../api'

export const EMPTY_FILTERS = { search: '', brand: '', product: '', sentiment: '', rating: '', date_from: '', date_to: '' }

/** Shared filter controls. `value` is an object like EMPTY_FILTERS. */
export default function FilterBar({ value, onChange, showSearch = true }) {
  const [opts, setOpts] = useState(null)
  const [search, setSearch] = useState(value.search || '')
  useEffect(() => { api.filterOptions().then(setOpts).catch(() => setOpts(null)) }, [])
  useEffect(() => setSearch(value.search || ''), [value.search])

  const set = (k) => (e) => onChange({ ...value, [k]: e.target.value })
  const products = (opts?.products || [])
  const active = Object.values(value).some((v) => v)

  return (
    <div className="card" style={{ padding: 12, marginBottom: 16 }}>
      <div className="row" style={{ alignItems: 'flex-end' }}>
        {showSearch && (
          <form onSubmit={(e) => { e.preventDefault(); onChange({ ...value, search }) }} className="row" style={{ gap: 6, flex: '1 1 240px' }}>
            <input type="search" placeholder="Search review text, title, product or brand…" value={search}
              onChange={(e) => setSearch(e.target.value)} style={{ flex: 1 }} aria-label="Search" />
            <button className="btn" type="submit"><Search size={15} /> Search</button>
          </form>
        )}
        <select value={value.brand} onChange={set('brand')} aria-label="Brand">
          <option value="">All brands</option>
          {(opts?.brands || []).map((b) => <option key={b}>{b}</option>)}
        </select>
        <select value={value.product} onChange={set('product')} aria-label="Product" style={{ maxWidth: 240 }}>
          <option value="">All products</option>
          {products.map((p) => <option key={p} value={p}>{p.length > 60 ? p.slice(0, 60) + '…' : p}</option>)}
        </select>
        <select value={value.sentiment} onChange={set('sentiment')} aria-label="Sentiment">
          <option value="">All sentiments</option>
          {['positive', 'neutral', 'negative', 'unlabeled'].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
        </select>
        <select value={value.rating} onChange={set('rating')} aria-label="Rating">
          <option value="">All ratings</option>
          {(opts?.ratings || []).map((r) => <option key={r} value={r}>{r} ★</option>)}
        </select>
        <input type="date" value={value.date_from} onChange={set('date_from')} min={opts?.date_min || undefined} max={opts?.date_max || undefined} aria-label="From date" title="From date" />
        <input type="date" value={value.date_to} onChange={set('date_to')} min={opts?.date_min || undefined} max={opts?.date_max || undefined} aria-label="To date" title="To date" />
        {active && <button className="btn ghost" onClick={() => onChange({ ...EMPTY_FILTERS })}><RotateCcw size={14} /> Reset</button>}
      </div>
      {(value.date_from || value.date_to) && <div className="small muted mt-s">Date filters exclude reviews without a date.</div>}
    </div>
  )
}

/** Convert filter state into query parameters understood by the API. */
export function toParams(f) {
  const p = {}
  Object.entries(f).forEach(([k, v]) => { if (v !== '' && v != null) p[k] = v })
  return p
}
