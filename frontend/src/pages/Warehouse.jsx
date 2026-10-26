import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowDownRight, ArrowUpLeft, Boxes, ChevronRight, Code2, Layers, Play, RefreshCw, Scissors } from 'lucide-react'
import { api } from '../api'
import { Alert, Card, ErrorBox, Loading, Pill, SENT_COLORS, SENTIMENTS, fmt, tooltipStyle, useAsync } from '../components/ui'

const DIM_LABEL = { year: 'Year', quarter: 'Quarter', month: 'Month', brand: 'Brand', product: 'Product', sentiment: 'Sentiment', rating: 'Rating' }

export default function WarehousePage() {
  const schema = useAsync(() => api.schema(), [])
  const runs = useAsync(() => api.etlRuns(), [])
  const [tab, setTab] = useState('hier')

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Data Warehouse</h1>
          <p>Logical star schema stored as MongoDB collections, the ETL history that populated it, and an OLAP workbench that runs real aggregation pipelines.</p>
        </div>
        <button className="btn" onClick={() => { schema.reload(); runs.reload() }}><RefreshCw size={15} /> Refresh</button>
      </div>

      {schema.error ? <ErrorBox error={schema.error} onRetry={schema.reload} /> : !schema.data ? <Loading /> : <Schema s={schema.data} />}

      <Card title="ETL runs" sub="Extract → Transform → Load" className="mt">
        {runs.error ? <ErrorBox error={runs.error} /> : !runs.data ? <Loading /> : runs.data.length === 0 ? <div className="small muted">No ETL runs yet — import a dataset.</div> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Started</th><th>Source</th><th>Status</th><th className="num">Extracted</th><th className="num">Transformed</th><th className="num">Loaded</th><th className="num">Dupes skipped</th><th>Labels</th><th className="num">Time</th></tr></thead>
            <tbody>{runs.data.map((r) => (
              <tr key={r._id}>
                <td className="small">{fmt.date(r.started_at)}</td>
                <td>{r.source}</td>
                <td><Pill value={r.status} kind={r.status === 'success' ? 'ok' : r.status === 'failed' ? 'err' : 'warn'} />{r.error && <div className="small" style={{ color: 'var(--err)' }}>{r.error}</div>}</td>
                <td className="num">{fmt.int(r.extract?.rows_read)}</td>
                <td className="num">{fmt.int(r.transform?.rows_out)}</td>
                <td className="num">{fmt.int(r.load?.inserted)}</td>
                <td className="num">{fmt.int((r.load?.duplicates_already_in_db || 0) + (r.transform?.duplicates_in_file || 0))}</td>
                <td className="small">{r.transform?.label_source}</td>
                <td className="num small">{r.duration_ms != null ? `${r.duration_ms} ms` : '—'}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>

      <h2 className="mt" style={{ fontSize: 17, marginTop: 28 }}>OLAP workbench</h2>
      <p className="small muted" style={{ margin: '4px 0 12px' }}>Measures: review count, average rating, average review length, and positive / neutral / negative counts.</p>
      <div className="tabs">
        {[['hier', 'Roll-up & Drill-down', Layers], ['slice', 'Slice', Scissors], ['dice', 'Dice', Boxes], ['cube', 'Custom cube', Code2]].map(([k, l, I]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}><I size={14} style={{ verticalAlign: -2, marginRight: 6 }} />{l}</button>
        ))}
      </div>
      {tab === 'hier' && <Hierarchy hierarchies={schema.data?.hierarchies} />}
      {tab === 'slice' && <Slice />}
      {tab === 'dice' && <Dice />}
      {tab === 'cube' && <Cube />}
    </>
  )
}

function Node({ title, count, items, keyField, className = '' }) {
  return (
    <div className={`node ${className}`}>
      <h5><span>{title}</span><span style={{ fontWeight: 400, opacity: .8 }}>{fmt.int(count)} docs</span></h5>
      <ul>{items.map((i) => <li key={i} className={i === keyField || i.endsWith('_key') ? 'k' : ''}>{i}</li>)}</ul>
    </div>
  )
}

function Schema({ s }) {
  const c = s.counts
  return (
    <div className="grid g3">
      <Card title="Logical star schema" className="span2">
        <div className="star" style={{ gridTemplateRows: 'auto auto' }}>
          <div style={{ gridColumn: 1, gridRow: 1 }}><Node title="dim_product" count={c.dim_product} items={['_id = product_key', 'product_name', 'brand', 'brand_key']} /></div>
          <div style={{ gridColumn: 1, gridRow: 2 }}><Node title="dim_brand" count={c.dim_brand} items={['_id = brand_key', 'brand']} /></div>
          <div className="node fact" style={{ gridRow: '1 / span 2' }}>
            <h5><span>fact_reviews</span><span style={{ fontWeight: 400 }}>{fmt.int(c.fact_reviews)} docs</span></h5>
            <ul>
              <li className="k">product_key → dim_product</li><li className="k">brand_key → dim_brand</li>
              <li className="k">date_key → dim_date</li><li className="k">sentiment_key → dim_sentiment</li>
              <li style={{ marginTop: 6 }}>rating · review_length (measures)</li>
              <li>sentiment · sentiment_source</li>
              <li style={{ marginTop: 6 }}>brand · product_name · year</li><li>quarter_label · year_month (denormalised)</li>
              <li style={{ marginTop: 6 }}>review_title · review · cleaned_review</li><li>dataset_id (lineage)</li>
            </ul>
          </div>
          <div style={{ gridColumn: 3, gridRow: 1 }}><Node title="dim_date" count={c.dim_date} items={['_id = date_key', 'date', 'year', 'quarter', 'month · month_name', 'day · weekday']} /></div>
          <div style={{ gridColumn: 3, gridRow: 2 }}><Node title="dim_sentiment" count={c.dim_sentiment} items={['_id = sentiment_key', 'label', 'rating_rule']} /></div>
        </div>
        <div className="mt"><Alert kind="info">{s.note}</Alert></div>
      </Card>
      <Card title="Collections">
        <div className="table-wrap"><table>
          <thead><tr><th>Collection</th><th className="num">Documents</th></tr></thead>
          <tbody>{Object.entries(c).map(([k, v]) => <tr key={k}><td className="mono small">{k}</td><td className="num">{fmt.int(v)}</td></tr>)}</tbody>
        </table></div>
        <div className="small muted mt">
          Storage: <strong>{s.storage.mode === 'mongodb' ? `MongoDB (${s.storage.database})` : s.storage.mode === 'memory' ? 'in-memory demo store — not persisted' : s.storage.mode}</strong>
        </div>
        <h4 className="mt" style={{ fontSize: 13 }}>Hierarchies</h4>
        {Object.entries(s.hierarchies).map(([h, lv]) => <div key={h} className="small"><strong>{h}:</strong> all → {lv.join(' → ')}</div>)}
        <details className="mt"><summary className="small" style={{ cursor: 'pointer' }}>Sample fact document</summary>
          <pre className="code mt-s">{JSON.stringify(s.samples.fact_reviews, null, 2)}</pre></details>
      </Card>
    </div>
  )
}

function OlapResult({ res, onRowClick, clickable }) {
  const [showPipe, setShowPipe] = useState(false)
  if (!res) return null
  const dims = res.group_by
  const label = (r) => dims.map((d) => r[d]).join(' · ') || 'All'
  const chart = res.rows.slice(0, 30).map((r) => ({ ...r, _label: label(r).slice(0, 28) }))
  return (
    <div className="stack mt" style={{ gap: 12 }}>
      <div className="row between">
        <div className="small"><Pill value={res.operation || 'cube'} kind="accent" /> {res.description}</div>
        <button className="btn sm" onClick={() => setShowPipe(!showPipe)}><Code2 size={14} /> {showPipe ? 'Hide' : 'Show'} aggregation pipeline</button>
      </div>
      {showPipe && <pre className="code">{`db.fact_reviews.aggregate(${JSON.stringify(res.pipeline, null, 2)})`}</pre>}
      {res.rows.length === 0 ? <div className="empty"><h4>No data in this cube region</h4>Try other values.</div> : (
        <div className="grid g2">
          <div className="table-wrap card" style={{ maxHeight: 420, overflowY: 'auto' }}>
            <table>
              <thead><tr>{dims.map((d) => <th key={d}>{DIM_LABEL[d]}</th>)}{dims.length === 0 && <th>Level</th>}<th className="num">Reviews</th><th className="num">Avg rating</th><th className="num">Pos</th><th className="num">Neu</th><th className="num">Neg</th><th className="num">Pos %</th>{clickable && <th />}</tr></thead>
              <tbody>{res.rows.map((r, i) => (
                <tr key={i} className={clickable ? 'clickable' : ''} onClick={() => clickable && onRowClick(r)}>
                  {dims.map((d) => <td key={d}>{d === 'sentiment' ? <Pill value={r[d]} /> : <span title={String(r[d])}>{String(r[d]).length > 48 ? String(r[d]).slice(0, 48) + '…' : r[d]}</span>}</td>)}
                  {dims.length === 0 && <td>ALL</td>}
                  <td className="num">{fmt.int(r.review_count)}</td><td className="num">{fmt.num(r.avg_rating)}</td>
                  <td className="num">{r.positive}</td><td className="num">{r.neutral}</td><td className="num">{r.negative}</td>
                  <td className="num">{fmt.pct(r.positive_pct)}</td>
                  {clickable && <td><ChevronRight size={14} color="var(--muted)" /></td>}
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="card" style={{ padding: 12 }}>
            <ResponsiveContainer key={res.description + res.rows.length} width="100%" height={Math.min(420, Math.max(220, chart.length * 26))}>
              <BarChart data={chart} layout="vertical" margin={{ left: 0, right: 12 }}>
                <CartesianGrid horizontal={false} stroke="#eef0f3" />
                <XAxis type="number" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="_label" width={150} tickLine={false} axisLine={false} fontSize={11} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#f4f5f8' }} />
                {SENTIMENTS.map((s) => <Bar key={s} dataKey={s} stackId="a" fill={SENT_COLORS[s]} name={s} isAnimationActive={false} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      {res.total_groups > res.rows.length && <div className="small muted">Showing {res.rows.length} of {res.total_groups} groups.</div>}
    </div>
  )
}

function useRunner() {
  const [res, setRes] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const run = (p) => { setBusy(true); setError(null); return p.then(setRes).catch(setError).finally(() => setBusy(false)) }
  return { res, error, busy, run }
}

function Hierarchy({ hierarchies }) {
  const [h, setH] = useState('date')
  const [stack, setStack] = useState([{ level: 'year', member: null }])
  const [total, setTotal] = useState(false)
  const { res, error, busy, run } = useRunner()
  const levels = hierarchies?.[h] || ['year', 'quarter', 'month']

  useEffect(() => { setStack([{ level: levels[0], member: null }]); setTotal(false) }, [h, hierarchies])  // eslint-disable-line
  useEffect(() => {
    if (total) { run(api.rollup({ hierarchy: h, level: 'all' })); return }
    const top = stack[stack.length - 1]
    if (stack.length === 1) run(api.rollup({ hierarchy: h, level: top.level }))
    else run(api.drilldown({ hierarchy: h, level: stack[stack.length - 2].level, member: top.member }))
  }, [stack, total])  // eslint-disable-line

  const depth = stack.length - 1
  const canDrill = !total && depth + 1 < levels.length
  const drill = (row) => {
    const cur = stack[stack.length - 1].level
    if (!canDrill || row[cur] === 'Unknown') return
    setStack([...stack, { level: levels[depth + 1], member: String(row[cur]) }])
  }
  const rollUp = () => { if (total) return; if (stack.length > 1) setStack(stack.slice(0, -1)); else setTotal(true) }

  return (
    <Card>
      <div className="row between">
        <div className="row">
          <span className="small" style={{ fontWeight: 600 }}>Hierarchy</span>
          <select value={h} onChange={(e) => setH(e.target.value)}>
            {Object.entries(hierarchies || { date: levels }).map(([k, lv]) => <option key={k} value={k}>{k}: {lv.join(' → ')}</option>)}
          </select>
        </div>
        <div className="row">
          <button className="btn" onClick={rollUp} disabled={total || busy}><ArrowUpLeft size={15} /> Roll up</button>
          <button className="btn" onClick={() => setTotal(false)} disabled={!total || busy}><ArrowDownRight size={15} /> Back down</button>
        </div>
      </div>
      <div className="breadcrumb mt">
        <button onClick={() => setTotal(true)}>ALL</button>
        {!total && stack.map((s, i) => (
          <span key={i} className="row" style={{ gap: 6 }}>
            <ChevronRight size={14} color="var(--muted)" />
            {s.member && <><button onClick={() => setStack(stack.slice(0, i))}>{s.member}</button><ChevronRight size={14} color="var(--muted)" /></>}
            <strong>{DIM_LABEL[s.level]}</strong>
          </span>
        ))}
      </div>
      <div className="small muted mt-s">
        {total ? 'Rolled up to the grand total (no grouping).' : canDrill ? `Click a row to drill down into ${DIM_LABEL[levels[depth + 1]].toLowerCase()}s.` : 'Finest level of this hierarchy reached.'}
      </div>
      {error && <div className="mt"><ErrorBox error={error} /></div>}
      {busy && !res ? <Loading /> : <OlapResult res={res} clickable={canDrill} onRowClick={drill} />}
    </Card>
  )
}

function useOptions() {
  const { data } = useAsync(() => api.filterOptions(), [])
  return {
    sentiment: ['positive', 'neutral', 'negative', 'unlabeled'],
    brand: data?.brands || [], product: data?.products || [], year: data?.years || [], rating: data?.ratings || [],
  }
}

function GroupBy({ value, onChange, exclude = [] }) {
  const dims = Object.keys(DIM_LABEL).filter((d) => !exclude.includes(d))
  return (
    <div className="row">
      <span className="small" style={{ fontWeight: 600 }}>Group by</span>
      {[0, 1].map((i) => (
        <select key={i} value={value[i] || ''} onChange={(e) => {
          const next = [...value]; next[i] = e.target.value; onChange(next.filter(Boolean).filter((d, j, a) => a.indexOf(d) === j))
        }}>
          <option value="">{i === 0 ? '— none —' : '— (optional) —'}</option>
          {dims.map((d) => <option key={d} value={d}>{DIM_LABEL[d]}</option>)}
        </select>
      ))}
    </div>
  )
}

function Slice() {
  const opts = useOptions()
  const [dim, setDim] = useState('sentiment')
  const [val, setVal] = useState('negative')
  const [groupBy, setGroupBy] = useState(['product'])
  const { res, error, busy, run } = useRunner()
  const values = opts[dim] || []
  const go = () => run(api.slice({ dimension: dim, value: val, group_by: groupBy.filter((g) => g !== dim) }))
  return (
    <Card>
      <p className="small muted" style={{ marginTop: 0 }}>A <strong>slice</strong> fixes one dimension to a single value (e.g. sentiment = negative) and analyses the remaining sub-cube.</p>
      <div className="row">
        <span className="small" style={{ fontWeight: 600 }}>Slice where</span>
        <select value={dim} onChange={(e) => { setDim(e.target.value); setVal('') }}>
          {['sentiment', 'brand', 'product', 'year', 'rating'].map((d) => <option key={d} value={d}>{DIM_LABEL[d]}</option>)}
        </select>
        <span>=</span>
        <select value={val} onChange={(e) => setVal(e.target.value)} style={{ maxWidth: 280 }}>
          <option value="">Choose…</option>
          {values.map((v) => <option key={v} value={v}>{String(v)}</option>)}
        </select>
        <GroupBy value={groupBy} onChange={setGroupBy} exclude={[dim]} />
        <button className="btn primary" disabled={!val || busy} onClick={go}><Play size={14} /> Run slice</button>
      </div>
      {error && <div className="mt"><ErrorBox error={error} /></div>}
      <OlapResult res={res} />
    </Card>
  )
}

function Dice() {
  const opts = useOptions()
  const [sel, setSel] = useState({ brand: [], sentiment: ['negative', 'neutral'], year: [], rating: [] })
  const [groupBy, setGroupBy] = useState(['year', 'sentiment'])
  const { res, error, busy, run } = useRunner()
  useEffect(() => { if (opts.year.length && !sel.year.length) setSel((s) => ({ ...s, year: opts.year.slice(-2) })) }, [opts.year.length])  // eslint-disable-line
  const toggle = (dim, v) => setSel((s) => ({ ...s, [dim]: s[dim].includes(v) ? s[dim].filter((x) => x !== v) : [...s[dim], v] }))
  const activeDims = Object.values(sel).filter((v) => v.length).length
  return (
    <Card>
      <p className="small muted" style={{ marginTop: 0 }}>A <strong>dice</strong> selects a sub-cube by choosing value sets on two or more dimensions at once.</p>
      <div className="grid g4">
        {Object.keys(sel).map((dim) => (
          <div key={dim}>
            <div className="small" style={{ fontWeight: 600, marginBottom: 4 }}>{DIM_LABEL[dim]} {sel[dim].length > 0 && <span className="muted">({sel[dim].length})</span>}</div>
            <div className="stack" style={{ gap: 3, maxHeight: 150, overflowY: 'auto' }}>
              {opts[dim].map((v) => (
                <label key={v} className="check"><input type="checkbox" checked={sel[dim].includes(v)} onChange={() => toggle(dim, v)} /> {String(v)}</label>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="row mt">
        <GroupBy value={groupBy} onChange={setGroupBy} />
        <button className="btn primary" disabled={activeDims < 2 || busy} onClick={() => run(api.dice({ selections: sel, group_by: groupBy }))}><Play size={14} /> Run dice</button>
        {activeDims < 2 && <span className="small muted">Select values on at least two dimensions.</span>}
      </div>
      {error && <div className="mt"><ErrorBox error={error} /></div>}
      <OlapResult res={res} />
    </Card>
  )
}

function Cube() {
  const [groupBy, setGroupBy] = useState(['brand', 'sentiment'])
  const [sortBy, setSortBy] = useState('dimension')
  const { res, error, busy, run } = useRunner()
  return (
    <Card>
      <p className="small muted" style={{ marginTop: 0 }}>Group the fact data by any one or two dimensions — the building block behind every OLAP operation.</p>
      <div className="row">
        <GroupBy value={groupBy} onChange={setGroupBy} />
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}><option value="dimension">Sort by dimension</option><option value="count">Sort by review count</option></select>
        <button className="btn primary" disabled={busy} onClick={() => run(api.cube({ group_by: groupBy, sort_by: sortBy, limit: 200 }))}><Play size={14} /> Run</button>
      </div>
      {error && <div className="mt"><ErrorBox error={error} /></div>}
      <OlapResult res={res} />
    </Card>
  )
}
