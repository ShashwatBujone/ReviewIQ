import { useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Database, Smile, Star, ThumbsDown } from 'lucide-react'
import { api } from '../api'
import FilterBar, { EMPTY_FILTERS, toParams } from '../components/FilterBar'
import { Card, Empty, ErrorBox, Loading, SENT_COLORS, SENTIMENTS, Seg, Stat, fmt, tooltipStyle, useAsync } from '../components/ui'

const short = (s, n = 34) => (s && s.length > n ? s.slice(0, n) + '…' : s)
const StackBars = ({ horizontal }) => SENTIMENTS.map((s, i) => (
  <Bar key={s} dataKey={s} stackId="s" fill={SENT_COLORS[s]} name={s[0].toUpperCase() + s.slice(1)}
    radius={i === 2 ? (horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]) : 0} />
))

export default function Insights() {
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [gran, setGran] = useState('month')
  const [topN, setTopN] = useState(10)
  const params = toParams(filters)
  const { data, error, loading, reload } = useAsync(
    () => api.analytics({ ...params, granularity: gran, top_n: topN }), [JSON.stringify(params), gran, topN])

  const o = data?.overall
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Insights &amp; Analytics</h1>
          <p>Sentiment broken down by product, brand, rating and time. Each chart is a MongoDB aggregation over the filtered fact data.</p>
        </div>
      </div>
      <FilterBar value={filters} onChange={setFilters} />

      {error ? <ErrorBox error={error} onRetry={reload} /> : !data ? <Loading /> : !o ? (
        <Card><Empty title="No reviews match these filters">Adjust the filters or import data.</Empty></Card>
      ) : (
        <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .15s' }}>
          <div className="grid g4">
            <Stat icon={Database} label="Reviews in selection" value={fmt.int(o.review_count)} />
            <Stat icon={Smile} label="Positive" value={fmt.pct(o.positive_pct)} color={SENT_COLORS.positive} note={`${fmt.int(o.positive)} reviews`} />
            <Stat icon={ThumbsDown} label="Negative" value={fmt.pct(o.negative_pct)} color={SENT_COLORS.negative} note={`${fmt.int(o.negative)} reviews`} />
            <Stat icon={Star} label="Average rating" value={o.avg_rating == null ? '—' : fmt.num(o.avg_rating)} note={`avg ${fmt.num(o.avg_review_length, 0)} words per review`} />
          </div>

          <Card title="Sentiment over time" className="mt" actions={<Seg value={gran} onChange={setGran} options={[['year', 'Year'], ['quarter', 'Quarter'], ['month', 'Month']]} />}>
            {data.trend.length === 0 ? <div className="muted small">No dated reviews in this selection.</div> : (
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={data.trend}>
                  <CartesianGrid vertical={false} stroke="#eef0f3" />
                  <XAxis dataKey={gran} tickLine={false} axisLine={false} fontSize={12} minTickGap={12} />
                  <YAxis yAxisId="c" tickLine={false} axisLine={false} width={40} />
                  <YAxis yAxisId="r" orientation="right" domain={[1, 5]} tickLine={false} axisLine={false} width={30} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend iconType="circle" />
                  {SENTIMENTS.map((s, i) => <Bar key={s} yAxisId="c" dataKey={s} stackId="s" fill={SENT_COLORS[s]} name={s[0].toUpperCase() + s.slice(1)} radius={i === 2 ? [3, 3, 0, 0] : 0} />)}
                  <Line yAxisId="r" type="linear" dataKey="avg_rating" name="Avg rating (right axis)" stroke="#4f46e5" strokeWidth={1.5} dot={{ r: 2 }} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
            <div className="small muted">Periods with only a few reviews make the average-rating line jump; compare it with the bar heights.</div>
            {data.unknown_date_reviews > 0 && <div className="small muted">{fmt.int(data.unknown_date_reviews)} reviews without a date are not shown in the trend.</div>}
          </Card>

          <div className="grid g2 mt">
            <Card title="Sentiment by product" sub={`top ${topN} by review count`} actions={
              <select value={topN} onChange={(e) => setTopN(Number(e.target.value))} aria-label="Top N">{[5, 10, 15, 25].map((n) => <option key={n} value={n}>Top {n}</option>)}</select>}>
              <ResponsiveContainer width="100%" height={Math.max(220, data.by_product.length * 32)}>
                <BarChart data={data.by_product.map((r) => ({ ...r, name: short(r.product) }))} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid horizontal={false} stroke="#eef0f3" />
                  <XAxis type="number" tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="name" width={190} tickLine={false} axisLine={false} fontSize={11.5} />
                  <Tooltip contentStyle={tooltipStyle} labelFormatter={(_, p) => p?.[0]?.payload?.product} />
                  <Legend iconType="circle" />
                  {StackBars({ horizontal: true })}
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <div className="stack">
              <Card title="Sentiment by brand">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={data.by_brand}>
                    <CartesianGrid vertical={false} stroke="#eef0f3" />
                    <XAxis dataKey="brand" tickLine={false} axisLine={false} />
                    <YAxis tickLine={false} axisLine={false} width={40} />
                    <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#f4f5f8' }} />
                    {StackBars({})}
                  </BarChart>
                </ResponsiveContainer>
                <div className="table-wrap"><table>
                  <thead><tr><th>Brand</th><th className="num">Reviews</th><th className="num">Avg rating</th><th className="num">Positive %</th><th className="num">Negative %</th></tr></thead>
                  <tbody>{data.by_brand.map((b) => (
                    <tr key={b.brand}><td>{b.brand}</td><td className="num">{fmt.int(b.review_count)}</td><td className="num">{fmt.num(b.avg_rating)}</td><td className="num">{fmt.pct(b.positive_pct)}</td><td className="num">{fmt.pct(b.negative_pct)}</td></tr>
                  ))}</tbody>
                </table></div>
              </Card>
              <Card title="Sentiment by rating">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={data.by_rating.map((r) => ({ ...r, label: r.rating === 'Unknown' ? 'n/a' : `${r.rating}★` }))}>
                    <CartesianGrid vertical={false} stroke="#eef0f3" />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} />
                    <YAxis tickLine={false} axisLine={false} width={40} />
                    <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#f4f5f8' }} />
                    {StackBars({})}
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
