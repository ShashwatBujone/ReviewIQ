import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Database, Download, PlayCircle, RefreshCw, Trash2, UploadCloud } from 'lucide-react'
import { api, fileUrl } from '../api'
import { useHealth } from '../components/Layout'
import { Alert, Card, Empty, ErrorBox, Loading, Pill, Seg, fmt, useAsync } from '../components/ui'

const FIELD_LABELS = {
  review: 'Review text *', review_title: 'Review title', rating: 'Rating (1–5)', product_name: 'Product name',
  brand: 'Brand', review_date: 'Review date', sentiment: 'Sentiment label',
}

export default function Datasets() {
  const { refresh } = useHealth()
  const list = useAsync(() => api.datasets(), [])
  const [current, setCurrent] = useState(null) // uploaded dataset being mapped
  const [busy, setBusy] = useState('')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const after = () => { list.reload(); refresh() }

  const importSample = async () => {
    setBusy('sample'); setError(null); setResult(null)
    try { const r = await api.importSample(); setResult(r.etl); after() } catch (e) { setError(e) } finally { setBusy('') }
  }
  const remove = async (id) => {
    if (!window.confirm('Delete this dataset and the reviews it loaded into the warehouse?')) return
    try { await api.deleteDataset(id); after(); if (current?._id === id) setCurrent(null) } catch (e) { setError(e) }
  }
  const reset = async () => {
    if (!window.confirm('Delete ALL reviews, dimensions, datasets and ETL history? Trained models are kept.')) return
    try { await api.resetWarehouse(); setCurrent(null); setResult(null); after() } catch (e) { setError(e) }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dataset Management</h1>
          <p>Upload a CSV, check the validation report, map its columns to ReviewIQ fields and run the ETL into the warehouse.</p>
        </div>
        <div className="row">
          <a className="btn" href={fileUrl('/api/datasets/sample/download')}><Download size={15} /> Sample CSV</a>
          <button className="btn" onClick={importSample} disabled={!!busy}>
            {busy === 'sample' ? <div className="spinner" /> : <Database size={15} />} Import sample dataset
          </button>
        </div>
      </div>

      {error && <div style={{ marginBottom: 16 }}><ErrorBox error={error} /></div>}
      {result && <div style={{ marginBottom: 16 }}><EtlResult r={result} /></div>}

      <div className="grid g3">
        <Uploader onUploaded={(d) => { setCurrent(d); setResult(null); list.reload() }} />
        <Card title="Expected columns" className="span2">
          <p className="small" style={{ marginTop: 0 }}>Only a review-text column is required. Column names are auto-detected (e.g. <span className="mono">review</span>, <span className="mono">text</span>, <span className="mono">reviews.text</span>) and can be changed in the mapping step.</p>
          <div className="table-wrap"><table>
            <thead><tr><th>Field</th><th>Used for</th></tr></thead>
            <tbody>
              <tr><td>review (required)</td><td>Model training and prediction, search</td></tr>
              <tr><td>rating</td><td>Averages; optional rating-derived labels (≤2 negative, 3 neutral, ≥4 positive)</td></tr>
              <tr><td>sentiment</td><td>Training labels (positive / neutral / negative)</td></tr>
              <tr><td>product_name, brand</td><td>Product & brand dimensions</td></tr>
              <tr><td>review_date</td><td>Date dimension (year → quarter → month)</td></tr>
              <tr><td>review_title</td><td>Displayed, and prepended to text for the models</td></tr>
            </tbody>
          </table></div>
        </Card>
      </div>

      {current && <MappingPanel key={current._id} dataset={current} onImported={(r) => { setResult(r); setCurrent(null); after() }} />}

      <Card title="Datasets" className="mt" actions={<>
        <button className="btn sm" onClick={list.reload}><RefreshCw size={14} /> Refresh</button>
        <button className="btn sm danger" onClick={reset}><Trash2 size={14} /> Reset warehouse</button>
      </>}>
        {list.error ? <ErrorBox error={list.error} onRetry={list.reload} /> : !list.data ? <Loading /> : list.data.length === 0 ? (
          <Empty title="No datasets yet">Upload a CSV or import the sample dataset.</Empty>
        ) : (
          <div className="table-wrap"><table>
            <thead><tr><th>File</th><th>Uploaded</th><th className="num">Rows</th><th className="num">In warehouse</th><th>Labels</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {list.data.map((d) => (
                <tr key={d._id}>
                  <td><strong>{d.filename}</strong><div className="small muted mono">{d._id}</div></td>
                  <td className="small">{fmt.date(d.uploaded_at)}</td>
                  <td className="num">{fmt.int(d.row_count)}</td>
                  <td className="num">{fmt.int(d.reviews_in_warehouse)}</td>
                  <td className="small">{d.label_source || d.validation?.label_source || '—'}</td>
                  <td><Pill value={d.status} kind={d.status === 'imported' ? 'ok' : 'warn'} /></td>
                  <td className="num" style={{ whiteSpace: 'nowrap' }}>
                    {d.status !== 'imported' && <button className="btn sm" onClick={() => api.dataset(d._id).then(setCurrent).catch(setError)}>Map & import</button>}{' '}
                    <button className="btn sm danger" onClick={() => remove(d._id)} aria-label="Delete dataset"><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

function Uploader({ onUploaded }) {
  const input = useRef()
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const upload = async (file) => {
    if (!file) return
    setBusy(true); setError(null)
    try { onUploaded(await api.upload(file)) } catch (e) { setError(e) } finally { setBusy(false); input.current.value = '' }
  }
  return (
    <Card title="Upload CSV">
      <div className={`dropzone ${drag ? 'drag' : ''}`} onClick={() => input.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files[0]) }}>
        {busy ? <Loading text="Uploading & validating…" /> : <>
          <UploadCloud size={30} color="var(--accent)" />
          <div style={{ fontWeight: 600, marginTop: 6 }}>Drop a CSV here or click to browse</div>
          <div className="small muted">UTF-8 / Windows-1252 · up to 25 MB</div>
        </>}
        <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => upload(e.target.files[0])} />
      </div>
      {error && <div className="mt"><ErrorBox error={error} /></div>}
    </Card>
  )
}

function ValidationReport({ v }) {
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="row">
        {v.ok ? <Pill value="valid" kind="ok" /> : <Pill value="invalid" kind="err" />}
        <span className="small muted">{fmt.int(v.row_count)} rows · {v.columns.length} columns · label source <strong>{v.label_source}</strong>
          {v.duplicate_rows != null && <> · {v.duplicate_rows} duplicate rows</>}
          {v.date_range && <> · {v.date_range[0]} → {v.date_range[1]}</>}</span>
      </div>
      {v.errors?.length > 0 && <Alert kind="err" title="Errors"><ul>{v.errors.map((e, i) => <li key={i}>{e}</li>)}</ul></Alert>}
      {v.warnings?.length > 0 && <Alert kind="warn" title="Warnings"><ul>{v.warnings.map((e, i) => <li key={i}>{e}</li>)}</ul></Alert>}
      {v.label_distribution && (
        <div className="row small">Labels:
          {Object.entries(v.label_distribution).map(([k, n]) => <span key={k}><Pill value={k} /> {fmt.int(n)}</span>)}
          {v.unlabeled_rows > 0 && <span><Pill value="unlabeled" /> {fmt.int(v.unlabeled_rows)}</span>}
        </div>
      )}
      {v.missing_by_column && (
        <div className="small muted">Missing values: {Object.entries(v.missing_by_column).filter(([, n]) => n > 0).map(([c, n]) => `${c} (${n})`).join(', ') || 'none'}</div>
      )}
    </div>
  )
}

function MappingPanel({ dataset, onImported }) {
  const [mapping, setMapping] = useState({ ...dataset.suggested_mapping })
  const [labelSource, setLabelSource] = useState('auto')
  const [mode, setMode] = useState('append')
  const [validation, setValidation] = useState(dataset.validation)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState(null)

  const revalidate = async (m = mapping, ls = labelSource) => {
    setBusy('validate'); setError(null)
    try { setValidation(await api.validate(dataset._id, { mapping: m, label_source: ls })) } catch (e) { setError(e) } finally { setBusy('') }
  }
  const setField = (f, col) => { const m = { ...mapping, [f]: col || null }; setMapping(m); revalidate(m) }
  const runImport = async () => {
    setBusy('import'); setError(null)
    try { onImported(await api.importDataset(dataset._id, { mapping, label_source: labelSource, mode })) } catch (e) { setError(e) } finally { setBusy('') }
  }

  return (
    <Card title={`Map columns · ${dataset.filename}`} className="mt">
      <div className="grid g2">
        <div className="stack">
          <div className="grid g2" style={{ gap: 10 }}>
            {dataset.fields.map((f) => (
              <label key={f} className="field">{FIELD_LABELS[f]}
                <select value={mapping[f] || ''} onChange={(e) => setField(f, e.target.value)}>
                  <option value="">— not mapped —</option>
                  {dataset.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            ))}
          </div>
          <div>
            <div className="small" style={{ fontWeight: 600, marginBottom: 6 }}>Sentiment label source</div>
            <Seg value={labelSource} onChange={(v) => { setLabelSource(v); revalidate(mapping, v) }}
              options={[['auto', 'Auto'], ['column', 'Sentiment column'], ['rating', 'Derive from rating'], ['none', 'No labels']]} />
            <div className="small muted mt-s">
              Rating rule: negative {dataset.rating_rule.negative}; neutral {dataset.rating_rule.neutral}; positive {dataset.rating_rule.positive}.
              {' '}{dataset.rating_rule.note} Rows without a valid label are kept for analytics but excluded from training.
            </div>
          </div>
          <div className="row">
            <span className="small" style={{ fontWeight: 600 }}>Load mode</span>
            <Seg value={mode} onChange={setMode} options={[['append', 'Append (skip duplicates)'], ['replace', 'Replace all reviews']]} />
          </div>
        </div>
        <div className="stack">
          {busy === 'validate' ? <Loading text="Validating…" /> : <ValidationReport v={validation} />}
          {error && <ErrorBox error={error} />}
          <div className="row">
            <button className="btn primary" onClick={runImport} disabled={!!busy || !validation.ok}>
              {busy === 'import' ? <div className="spinner" style={{ borderTopColor: '#fff' }} /> : <PlayCircle size={15} />} Run ETL import
            </button>
          </div>
        </div>
      </div>
      <h4 className="mt" style={{ fontSize: 13.5 }}>Preview (first {dataset.preview.length} rows)</h4>
      <div className="table-wrap mt-s"><table>
        <thead><tr>{dataset.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{dataset.preview.map((r, i) => (
          <tr key={i}>{dataset.columns.map((c) => <td key={c}><div className="truncate" style={{ maxWidth: 240 }}>{r[c] ?? <span className="muted">∅</span>}</div></td>)}</tr>
        ))}</tbody>
      </table></div>
    </Card>
  )
}

function EtlResult({ r }) {
  const t = r.transform, l = r.load
  return (
    <Alert kind="ok" title="ETL completed.">
      Extracted {fmt.int(r.extract.rows_read)} rows → transformed {fmt.int(t.rows_out)} reviews
      ({t.skipped_empty_review} empty skipped, {t.duplicates_in_file} in-file duplicates, {t.missing_dates} missing dates,
      {' '}{t.invalid_or_missing_ratings} missing/invalid ratings, {t.unlabeled} unlabeled; labels from <strong>{t.label_source}</strong>)
      → loaded <strong>{fmt.int(l.inserted)}</strong> new ({fmt.int(l.duplicates_already_in_db)} already in the warehouse) in {r.duration_ms} ms.
      {' '}<Link to="/models">Train models on the new data →</Link>
    </Alert>
  )
}
