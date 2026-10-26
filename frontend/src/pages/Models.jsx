import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BrainCircuit, Download, Play } from 'lucide-react'
import { api, fileUrl } from '../api'
import { useHealth } from '../components/Layout'
import { Alert, Card, Empty, ErrorBox, Loading, MODEL_COLORS, Pill, fmt, tooltipStyle, useAsync } from '../components/ui'

const DEFAULTS = { test_size: 0.2, random_state: 42, lr_C: 1, nb_alpha: 0.1, cv_folds: 5, ngram_max: 2,
  balance_classes: true, include_title: true, deduplicate: true }
const METRICS = [['accuracy', 'Accuracy'], ['precision_macro', 'Precision (macro)'], ['recall_macro', 'Recall (macro)'],
  ['f1_macro', 'F1 (macro)'], ['f1_weighted', 'F1 (weighted)']]

export default function Models() {
  const { refresh } = useHealth()
  const status = useAsync(() => api.modelStatus(), [])
  const runs = useAsync(() => api.modelRuns().catch(() => []), [])
  const [params, setParams] = useState(DEFAULTS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [fresh, setFresh] = useState(null)

  const train = async () => {
    setBusy(true); setError(null)
    try { setFresh(await api.train(params)); status.reload(); runs.reload(); refresh() } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const meta = fresh || status.data?.metadata
  const num = (k, step) => (e) => setParams({ ...params, [k]: step ? Number(e.target.value) : parseInt(e.target.value, 10) })

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Model Performance</h1>
          <p>Train TF-IDF + Logistic Regression and Multinomial Naive Bayes on the labeled reviews in the warehouse and compare them on a held-out, stratified test split.</p>
        </div>
        {meta && <a className="btn" href={fileUrl('/api/export/model-metrics')}><Download size={15} /> Metrics CSV</a>}
      </div>

      <Card title="Train models">
        <div className="row" style={{ alignItems: 'flex-end', gap: 14 }}>
          <label className="field">Test split<select value={params.test_size} onChange={num('test_size', true)}>{[0.15, 0.2, 0.25, 0.3].map((v) => <option key={v} value={v}>{v * 100}%</option>)}</select></label>
          <label className="field">LR regularisation C<input type="number" step="0.1" min="0.01" value={params.lr_C} onChange={num('lr_C', true)} style={{ width: 100 }} /></label>
          <label className="field">NB smoothing α<input type="number" step="0.05" min="0.01" value={params.nb_alpha} onChange={num('nb_alpha', true)} style={{ width: 100 }} /></label>
          <label className="field">N-grams<select value={params.ngram_max} onChange={num('ngram_max')}><option value={1}>Unigrams</option><option value={2}>Uni + bigrams</option><option value={3}>Up to trigrams</option></select></label>
          <label className="field">CV folds<select value={params.cv_folds} onChange={num('cv_folds')}>{[0, 3, 5, 10].map((v) => <option key={v} value={v}>{v || 'off'}</option>)}</select></label>
          <label className="field">Random seed<input type="number" value={params.random_state} onChange={num('random_state')} style={{ width: 90 }} /></label>
          <div className="stack" style={{ gap: 4 }}>
            <label className="check"><input type="checkbox" checked={params.balance_classes} onChange={(e) => setParams({ ...params, balance_classes: e.target.checked })} /> Balance classes</label>
            <label className="check"><input type="checkbox" checked={params.include_title} onChange={(e) => setParams({ ...params, include_title: e.target.checked })} /> Include title</label>
            <label className="check"><input type="checkbox" checked={params.deduplicate} onChange={(e) => setParams({ ...params, deduplicate: e.target.checked })} /> Drop duplicate texts</label>
          </div>
          <button className="btn primary" onClick={train} disabled={busy}>
            {busy ? <div className="spinner" style={{ borderTopColor: '#fff' }} /> : <Play size={15} />} {busy ? 'Training…' : 'Train & evaluate'}
          </button>
        </div>
        {error && <div className="mt"><ErrorBox error={error} /></div>}
        {status.data?.message && !error && <div className="mt"><Alert kind="warn">{status.data.message}</Alert></div>}
      </Card>

      {status.loading && !meta ? <Loading /> : !meta ? (
        <Card className="mt"><Empty title="No trained models">Import labeled data, then click <strong>Train &amp; evaluate</strong>.</Empty></Card>
      ) : <Results meta={meta} />}

      <Card title="Training history" sub="saved in the database" className="mt">
        {!runs.data?.length ? <div className="small muted">No runs recorded in the database yet.</div> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Trained</th><th>Run</th><th className="num">Train / Test</th><th className="num">LR acc</th><th className="num">LR F1</th><th className="num">NB acc</th><th className="num">NB F1</th><th>Best</th></tr></thead>
            <tbody>{runs.data.map((r) => (
              <tr key={r._id}>
                <td className="small">{fmt.date(r.trained_at)}</td><td className="mono small">{r._id}</td>
                <td className="num">{r.data.train_size} / {r.data.test_size}</td>
                <td className="num">{fmt.ratio(r.results.logistic_regression.accuracy)}</td><td className="num">{fmt.num(r.results.logistic_regression.f1_macro, 3)}</td>
                <td className="num">{fmt.ratio(r.results.naive_bayes.accuracy)}</td><td className="num">{fmt.num(r.results.naive_bayes.f1_macro, 3)}</td>
                <td>{r.results[r.best_model].name}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  )
}

function Results({ meta }) {
  const keys = Object.keys(meta.results)
  const chart = METRICS.map(([k, label]) => ({ metric: label, ...Object.fromEntries(keys.map((m) => [m, meta.results[m][k]])) }))
  const d = meta.data
  return (
    <>
      <Alert kind="info" title="How to read these numbers.">
        The test set has {d.test_size} reviews ({Object.entries(d.test_class_distribution).map(([k, v]) => `${v} ${k}`).join(', ')}).
        Always predicting “{meta.baseline.strategy.split("'")[1]}” already scores <strong>{fmt.ratio(meta.baseline.accuracy)}</strong> accuracy
        (macro F1 {fmt.num(meta.baseline.f1_macro, 3)}), so <strong>macro F1</strong>, which weighs every class equally, matters more than accuracy.
        The best model is chosen by {meta.selection_metric === 'cv_f1_macro_mean' ? 'cross-validated macro F1 on the training split, so the test set stays untouched for the final report' : 'test-set macro F1 (cross-validation was switched off)'}.
        Labels come from: {Object.entries(d.label_sources).map(([k, v]) => `${k.replace('_', ' ')} (${v})`).join(', ')}.
      </Alert>

      <div className="grid g2 mt">
        <Card title="Model comparison" sub={`trained ${fmt.date(meta.trained_at)}`}>
          <div className="table-wrap"><table>
            <thead><tr><th>Metric (test set)</th>{keys.map((k) => <th key={k} className="num">{meta.results[k].name}</th>)}<th className="num">Baseline</th></tr></thead>
            <tbody>
              {METRICS.map(([k, label]) => {
                const best = Math.max(...keys.map((m) => meta.results[m][k]))
                return (
                  <tr key={k}><td>{label}</td>
                    {keys.map((m) => <td key={m} className="num" style={{ fontWeight: meta.results[m][k] === best ? 700 : 400 }}>{fmt.num(meta.results[m][k], 3)}</td>)}
                    <td className="num muted">{k === 'accuracy' ? fmt.num(meta.baseline.accuracy, 3) : k === 'f1_macro' ? fmt.num(meta.baseline.f1_macro, 3) : ''}</td>
                  </tr>
                )
              })}
              {meta.results[keys[0]].cv_folds && (
                <tr><td>{meta.results[keys[0]].cv_folds}-fold CV F1 (train split)</td>
                  {keys.map((m) => <td key={m} className="num">{fmt.num(meta.results[m].cv_f1_macro_mean, 3)} ± {fmt.num(meta.results[m].cv_f1_macro_std, 3)}</td>)}<td /></tr>
              )}
            </tbody>
          </table></div>
          <div className="row mt small">Selected: <span className="pill accent"><BrainCircuit size={12} /> {meta.results[meta.best_model].name}</span> ({meta.selection_metric === 'cv_f1_macro_mean' ? 'highest cross-validated macro F1' : 'highest test macro F1'})</div>
        </Card>
        <Card title="Metric comparison">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chart} margin={{ left: -10 }}>
              <CartesianGrid vertical={false} stroke="#eef0f3" />
              <XAxis dataKey="metric" tickLine={false} axisLine={false} fontSize={11.5} interval={0} />
              <YAxis domain={[0, 1]} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => fmt.num(v, 3)} cursor={{ fill: '#f4f5f8' }} />
              <Legend iconType="circle" />
              {keys.map((k) => <Bar key={k} dataKey={k} name={meta.results[k].name} fill={MODEL_COLORS[k]} radius={[4, 4, 0, 0]} />)}
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid g2 mt">
        {keys.map((k) => (
          <Card key={k} title={meta.results[k].name} sub="confusion matrix & per-class metrics">
            <ConfusionMatrix cm={meta.results[k].confusion_matrix} color={MODEL_COLORS[k]} />
            <div className="table-wrap mt"><table>
              <thead><tr><th>Class</th><th className="num">Precision</th><th className="num">Recall</th><th className="num">F1</th><th className="num">Support</th></tr></thead>
              <tbody>{Object.entries(meta.results[k].per_class).map(([lab, m]) => (
                <tr key={lab}><td><Pill value={lab} /></td><td className="num">{fmt.num(m.precision, 3)}</td><td className="num">{fmt.num(m.recall, 3)}</td><td className="num">{fmt.num(m.f1, 3)}</td><td className="num">{m.support}</td></tr>
              ))}</tbody>
            </table></div>
            <h4 className="mt" style={{ fontSize: 13 }}>Most indicative terms per class</h4>
            {Object.entries(meta.results[k].top_features || {}).map(([lab, terms]) => (
              <div key={lab} className="row mt-s" style={{ alignItems: 'flex-start' }}>
                <div style={{ width: 78 }}><Pill value={lab} /></div>
                <div className="terms" style={{ flex: 1 }}>{terms.slice(0, 10).map((t) => <span key={t.term} className="term">{t.term}</span>)}</div>
              </div>
            ))}
          </Card>
        ))}
      </div>

      <Card title="Training data" className="mt">
        <dl className="kv">
          <dt>Labeled reviews in scope</dt><dd>{fmt.int(d.labeled_reviews)} of {fmt.int(d.reviews_in_scope)} ({fmt.int(d.excluded_unlabeled)} unlabeled excluded)</dd>
          <dt>Duplicate texts removed</dt><dd>{fmt.int(d.dropped_duplicate_texts)} (prevents the same text appearing in train and test){d.duplicate_texts_with_conflicting_labels ? `; ${d.duplicate_texts_with_conflicting_labels} had conflicting labels` : ''}</dd>
          <dt>Used for training</dt><dd>{fmt.int(d.used_for_training)} → train {fmt.int(d.train_size)} / test {fmt.int(d.test_size)} (stratified)</dd>
          <dt>Class distribution</dt><dd>{Object.entries(d.class_distribution).map(([k, v]) => `${k} ${v}`).join(' · ')}</dd>
          <dt>TF-IDF vocabulary</dt><dd>{fmt.int(d.vocabulary_size)} terms (min_df {d.tfidf_min_df}, n-grams 1–{meta.params.ngram_max}, sublinear tf)</dd>
          <dt>Class balancing</dt><dd>{meta.params.balance_classes ? 'On — LR class_weight="balanced", NB balanced sample weights' : 'Off'}</dd>
          <dt>scikit-learn</dt><dd>{meta.sklearn_version}</dd>
        </dl>
      </Card>
    </>
  )
}

function ConfusionMatrix({ cm, color }) {
  const max = Math.max(1, ...cm.matrix.flat())
  const n = cm.labels.length
  return (
    <div>
      <div className="small muted" style={{ marginBottom: 6 }}>Rows = actual, columns = predicted</div>
      <div className="cm" style={{ gridTemplateColumns: `80px repeat(${n}, 1fr)` }}>
        <div />
        {cm.labels.map((l) => <div key={l} className="cm-label">{l}</div>)}
        {cm.matrix.map((row, i) => [
          <div key={`l${i}`} className="cm-label">{cm.labels[i]}</div>,
          ...row.map((v, j) => {
            const a = v / max
            return <div key={`${i}-${j}`} className="cm-cell" title={`actual ${cm.labels[i]}, predicted ${cm.labels[j]}: ${v}`}
              style={{ background: i === j ? `color-mix(in srgb, ${color} ${15 + a * 75}%, white)` : `rgba(220,76,100,${0.06 + a * 0.5})`, color: a > 0.55 ? '#fff' : 'var(--text)' }}>{v}</div>
          }),
        ])}
      </div>
    </div>
  )
}
