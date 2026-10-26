import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, FileSpreadsheet, Sparkles, Trash2 } from 'lucide-react'
import { api, fileUrl, request, saveBlob } from '../api'
import { useHealth } from '../components/Layout'
import { Alert, Card, ErrorBox, MODEL_COLORS, Pill, ProbBar, SENT_COLORS, Seg, fmt, useAsync } from '../components/ui'

// Hand-written example inputs for trying the analyzer (not taken from the dataset).
const EXAMPLES = [
  'Setup took two minutes and the sound is crisp and loud. Absolutely love it!',
  'It works, but the battery only lasts a few hours. Decent for the price, nothing special.',
  'Stopped charging after a week and customer support never replied. Total waste of money.',
]

export default function Analyzer() {
  const { health, refresh } = useHealth()
  const [text, setText] = useState('')
  const [model, setModel] = useState('both')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const history = useAsync(() => api.predictionHistory(), [])

  const analyse = async (e) => {
    e?.preventDefault()
    if (!text.trim()) return
    setBusy(true); setError(null)
    try {
      setResult(await api.predict({ text, model }))
      history.reload(); refresh()
    } catch (err) { setError(err); setResult(null) } finally { setBusy(false) }
  }

  const notReady = health && !health.models?.ready

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Sentiment Analyzer</h1>
          <p>Type or paste a review. It is cleaned with the same pipeline used in training, converted to TF-IDF features and classified by the saved models.</p>
        </div>
      </div>

      {notReady && (
        <div style={{ marginBottom: 16 }}>
          <Alert kind="warn" title="Models are not trained yet.">
            {health.models.message} <Link to="/models">Train them on the Model Performance page →</Link>
          </Alert>
        </div>
      )}

      <div className="grid g2">
        <Card title="Review text">
          <form onSubmit={analyse} className="stack" style={{ gap: 12 }}>
            <textarea rows={7} value={text} onChange={(e) => setText(e.target.value)} maxLength={10000}
              placeholder="e.g. The speaker connects instantly and the sound quality is great…" aria-label="Review text" />
            <div className="row small muted">Try:
              {EXAMPLES.map((ex, i) => <button key={i} type="button" className="btn sm" onClick={() => setText(ex)}>Example {i + 1}</button>)}
            </div>
            <div className="row between">
              <Seg value={model} onChange={setModel} options={[['both', 'Compare both'], ['logistic_regression', 'Logistic Regression'], ['naive_bayes', 'Naive Bayes']]} />
              <button className="btn primary" disabled={busy || !text.trim() || notReady}>
                {busy ? <div className="spinner" style={{ borderTopColor: '#fff' }} /> : <Sparkles size={15} />} Analyse sentiment
              </button>
            </div>
          </form>
          {error && <div className="mt"><ErrorBox error={error} /></div>}
        </Card>

        <Card title="Prediction">
          {!result ? <div className="empty"><h4>No prediction yet</h4>Results from each model appear here.</div> : (
            <div className="stack">
              {result.warning && <Alert kind="warn">{result.warning}</Alert>}
              <div className={`grid ${Object.keys(result.predictions).length > 1 ? 'g2' : ''}`}>
                {Object.entries(result.predictions).map(([key, p]) => (
                  <div key={key} className="card" style={{ padding: 14, borderTop: `3px solid ${MODEL_COLORS[key]}` }}>
                    <div className="row between">
                      <strong className="small">{p.model}{result.best_model === key && <span className="pill accent" style={{ marginLeft: 6 }}>selected</span>}</strong>
                    </div>
                    <div className="row mt-s" style={{ alignItems: 'baseline' }}>
                      <Pill value={p.label} />
                      <span className="small muted">confidence <strong style={{ color: 'var(--text)' }}>{fmt.ratio(p.confidence)}</strong></span>
                    </div>
                    <div className="mt">
                      {Object.entries(p.probabilities).map(([lab, v]) => <ProbBar key={lab} label={lab} value={v} color={SENT_COLORS[lab]} />)}
                    </div>
                  </div>
                ))}
              </div>
              <dl className="kv">
                <dt>Cleaned text</dt><dd className="mono small" style={{ wordBreak: 'break-word' }}>{result.cleaned_text}</dd>
                <dt>Known vocabulary terms</dt><dd>{result.known_terms}</dd>
                <dt>Saved to history</dt><dd>{result.saved ? 'Yes' : 'No'}</dd>
              </dl>
              <div className="small muted">{result.confidence_note}</div>
            </div>
          )}
        </Card>
      </div>

      <div className="grid g3 mt">
        <Card title="Recent predictions" className="span2" actions={<>
          <a className="btn sm" href={fileUrl('/api/export/predictions')}><Download size={14} /> CSV</a>
          <button className="btn sm danger" onClick={() => request('/api/predict/history', { method: 'DELETE' }).then(history.reload)}><Trash2 size={14} /> Clear</button>
        </>}>
          {history.error ? <ErrorBox error={history.error} /> : !history.data?.length ? <div className="muted small">No saved predictions yet.</div> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>When</th><th>Text</th><th>Logistic Reg.</th><th>Naive Bayes</th></tr></thead>
                <tbody>
                  {history.data.map((h) => (
                    <tr key={h._id}>
                      <td className="small muted" style={{ whiteSpace: 'nowrap' }}>{fmt.date(h.created_at)}</td>
                      <td><div className="truncate">{h.text}</div></td>
                      {['logistic_regression', 'naive_bayes'].map((k) => (
                        <td key={k}>{h.predictions[k] ? <><Pill value={h.predictions[k].label} /> <span className="small muted">{fmt.ratio(h.predictions[k].confidence, 0)}</span></> : '—'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <BatchPredict disabled={notReady} />
      </div>
    </>
  )
}

function BatchPredict({ disabled }) {
  const ref = useRef()
  const [file, setFile] = useState(null)
  const [model, setModel] = useState('logistic_regression')
  const [col, setCol] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const run = async () => {
    setBusy(true); setError(null); setDone(false)
    try {
      const blob = await api.predictBatch(file, model, col.trim())
      saveBlob(blob, `predictions_${file.name}`)
      setDone(true)
    } catch (e) { setError(e) } finally { setBusy(false) }
  }

  return (
    <Card title="Batch prediction" sub="CSV in → CSV out">
      <div className="stack" style={{ gap: 10 }}>
        <p className="small muted" style={{ margin: 0 }}>Adds <span className="mono">predicted_sentiment</span> and <span className="mono">prediction_confidence</span> columns to every row.</p>
        <input ref={ref} type="file" accept=".csv" onChange={(e) => { setFile(e.target.files[0] || null); setDone(false) }} />
        <label className="field">Text column (optional — auto-detected)
          <input type="text" value={col} onChange={(e) => setCol(e.target.value)} placeholder="e.g. review" />
        </label>
        <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="Model">
          <option value="logistic_regression">Logistic Regression</option>
          <option value="naive_bayes">Multinomial Naive Bayes</option>
        </select>
        <button className="btn primary" disabled={!file || busy || disabled} onClick={run}>
          {busy ? <div className="spinner" style={{ borderTopColor: '#fff' }} /> : <FileSpreadsheet size={15} />} Predict & download
        </button>
        {done && <Alert kind="ok">Predictions downloaded.</Alert>}
        {error && <ErrorBox error={error} />}
      </div>
    </Card>
  )
}
