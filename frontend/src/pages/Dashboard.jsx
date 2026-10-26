import { Link } from 'react-router-dom'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Activity, BrainCircuit, Database, MessageSquareText, Package, Smile, Star, Upload } from 'lucide-react'
import { api } from '../api'
import { Card, Empty, ErrorBox, Loading, Pill, SENT_COLORS, SENTIMENTS, Stat, fmt, tooltipStyle, useAsync } from '../components/ui'

const ACT_ICON = { etl: Database, training: BrainCircuit, prediction: MessageSquareText }

export default function Dashboard() {
  const { data, error, loading, reload } = useAsync(() => api.dashboard(), [])
  if (loading && !data) return <Loading />
  if (error && !data) return <ErrorBox error={error} onRetry={reload} />
  const d = data

  const pie = [...SENTIMENTS, 'unlabeled'].map((s) => ({ name: s, value: d.sentiment[s] })).filter((x) => x.value > 0)
  const labeled = SENTIMENTS.reduce((a, s) => a + d.sentiment[s], 0)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Live overview of the review warehouse. Every number below is computed from the stored reviews and the latest trained models.</p>
        </div>
        <div className="row">
          <Link className="btn" to="/datasets"><Upload size={15} /> Import data</Link>
          <Link className="btn primary" to="/analyzer"><MessageSquareText size={15} /> Analyse a review</Link>
        </div>
      </div>

      {d.total_reviews === 0 ? (
        <Card><Empty title="No reviews in the warehouse yet" action={<Link className="btn primary" to="/datasets"><Upload size={15} /> Go to Dataset Management</Link>}>
          Upload a CSV or import the bundled sample dataset to populate the dashboard.
        </Empty></Card>
      ) : (
        <>
          <div className="grid g5">
            <Stat icon={Database} label="Total reviews" value={fmt.int(d.total_reviews)} note={`${d.datasets} dataset(s) imported`} />
            <Stat icon={Smile} label="Positive share" value={fmt.pct(d.positive_pct)} color={SENT_COLORS.positive} note={`of ${fmt.int(labeled)} labeled reviews`} />
            <Stat icon={Star} label="Average rating" value={d.avg_rating == null ? '—' : `${fmt.num(d.avg_rating)} / 5`} note="reviews with a valid rating" />
            <Stat icon={Package} label="Products · Brands" value={`${d.products} · ${d.brands}`} note="distinct in warehouse" />
            <Stat icon={BrainCircuit} label="Selected model · test macro F1" value={d.model ? fmt.num(d.model.f1_macro, 3) : '—'}
              note={d.model ? `${d.model.best_model} · acc ${fmt.ratio(d.model.accuracy)} (baseline ${fmt.ratio(d.model.baseline_accuracy)})` : <Link to="/models">Train models →</Link>} />
          </div>

          <div className="grid g3 mt">
            <Card title="Sentiment distribution" sub="labels as stored">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie data={pie} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={2} stroke="none">
                    {pie.map((p) => <Cell key={p.name} fill={SENT_COLORS[p.name]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [`${fmt.int(v)} (${((v / d.total_reviews) * 100).toFixed(1)}%)`, n]} />
                  <Legend iconType="circle" formatter={(v) => <span style={{ color: '#4a5263', textTransform: 'capitalize' }}>{v}</span>} />
                </PieChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Rating distribution">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={d.rating_distribution.map((r) => ({ ...r, label: r.rating === 'Unknown' ? 'n/a' : `${r.rating}★` }))}>
                  <CartesianGrid vertical={false} stroke="#eef0f3" />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} />
                  <YAxis tickLine={false} axisLine={false} width={40} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#f4f5f8' }} />
                  <Bar dataKey="count" name="Reviews" radius={[5, 5, 0, 0]}>
                    {d.rating_distribution.map((r) => (
                      <Cell key={r.rating} fill={r.rating === 'Unknown' ? SENT_COLORS.unlabeled : r.rating <= 2 ? SENT_COLORS.negative : r.rating >= 4 ? SENT_COLORS.positive : SENT_COLORS.neutral} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Recent activity" bodyClass="">
              {d.recent_activity.length === 0 ? <div className="muted small">No activity yet.</div> : (
                <ul className="activity">
                  {d.recent_activity.slice(0, 6).map((a, i) => {
                    const Icon = ACT_ICON[a.type] || Activity
                    return (
                      <li key={i}>
                        <div className="ico"><Icon size={15} /></div>
                        <div style={{ minWidth: 0 }}>
                          <div className="truncate">{a.text}</div>
                          <div className="small muted">{fmt.date(a.at)}</div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </Card>
          </div>

          <div className="grid g3 mt">
            <Card title="Monthly sentiment trend" sub="last 24 months with data" className="span2">
              {d.monthly_trend.length === 0 ? <div className="muted small">No dated reviews.</div> : (
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={d.monthly_trend}>
                    <CartesianGrid vertical={false} stroke="#eef0f3" />
                    <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} minTickGap={16} />
                    <YAxis tickLine={false} axisLine={false} width={40} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Legend iconType="circle" />
                    {SENTIMENTS.map((s) => (
                      <Area key={s} type="monotone" dataKey={s} stackId="1" stroke={SENT_COLORS[s]} fill={SENT_COLORS[s]} fillOpacity={0.75} name={s[0].toUpperCase() + s.slice(1)} />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Card>
            <Card title="Most reviewed products">
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Product</th><th className="num">Reviews</th><th className="num">Pos %</th></tr></thead>
                  <tbody>
                    {d.top_products.map((p) => (
                      <tr key={p.product}>
                        <td><div className="truncate" title={p.product} style={{ maxWidth: 220 }}>{p.product}</div></td>
                        <td className="num">{fmt.int(p.count)}</td>
                        <td className="num">{fmt.pct(p.positive_pct, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
          <p className="small muted mt">
            Sentiment labels come from the dataset's sentiment column or are derived from ratings (1–2 negative, 3 neutral,
            4–5 positive); either way they are proxies, not human annotations — the import report on Dataset Management says
            which applies. When one class such as <Pill value="positive" /> dominates, accuracy alone is misleading, so model
            accuracy is shown next to the majority-class baseline.
          </p>
        </>
      )}
    </>
  )
}
