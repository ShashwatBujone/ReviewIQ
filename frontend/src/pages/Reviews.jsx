import { Fragment, useState } from 'react'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { api, fileUrl } from '../api'
import FilterBar, { EMPTY_FILTERS, toParams } from '../components/FilterBar'
import { Card, Empty, ErrorBox, Loading, Pill, Stars, fmt, useAsync } from '../components/ui'

export default function Reviews() {
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [sort, setSort] = useState('date')
  const [order, setOrder] = useState('desc')
  const [open, setOpen] = useState(null)

  const params = toParams(filters)
  const { data, error, loading, reload } = useAsync(
    () => api.reviews({ ...params, page, page_size: pageSize, sort, order }),
    [JSON.stringify(params), page, pageSize, sort, order],
  )
  const update = (f) => { setFilters(f); setPage(1) }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Reviews Explorer</h1>
          <p>Browse the fact table. Search runs a case-insensitive match on review text, title and product name.</p>
        </div>
        <a className="btn" href={fileUrl('/api/export/reviews', params)}><Download size={15} /> Export filtered CSV</a>
      </div>

      <FilterBar value={filters} onChange={update} />

      <Card title={data ? `${fmt.int(data.total)} reviews` : 'Reviews'} actions={<>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by">
          {[['date', 'Date'], ['rating', 'Rating'], ['product', 'Product'], ['brand', 'Brand'], ['length', 'Length'], ['sentiment', 'Sentiment']].map(([v, l]) => <option key={v} value={v}>Sort: {l}</option>)}
        </select>
        <select value={order} onChange={(e) => setOrder(e.target.value)} aria-label="Order">
          <option value="desc">Descending</option><option value="asc">Ascending</option>
        </select>
      </>}>
        {error ? <ErrorBox error={error} onRetry={reload} /> : !data ? <Loading /> : data.items.length === 0 ? (
          <Empty title="No reviews match">Try removing some filters, or import a dataset first.</Empty>
        ) : (
          <>
            <div className="table-wrap" style={{ opacity: loading ? 0.55 : 1 }}>
              <table>
                <thead>
                  <tr><th>Date</th><th>Product</th><th>Review</th><th>Rating</th><th>Sentiment</th></tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <Fragment key={r._id}>
                      <tr className="clickable" onClick={() => setOpen(open === r._id ? null : r._id)}>
                        <td className="small" style={{ whiteSpace: 'nowrap' }}>{r.review_date || <span className="muted">unknown</span>}</td>
                        <td style={{ maxWidth: 220 }}><div className="truncate" title={r.product_name}>{r.product_name}</div><div className="small muted">{r.brand}</div></td>
                        <td>{r.review_title && <strong>{r.review_title} </strong>}<div className="truncate muted">{r.review}</div></td>
                        <td><Stars value={r.rating} /></td>
                        <td><Pill value={r.sentiment} />{r.sentiment_source === 'rating_derived' && <div className="small muted">from rating</div>}</td>
                      </tr>
                      {open === r._id && (
                        <tr><td colSpan={5} style={{ background: 'var(--surface-2)' }}>
                          <p style={{ margin: '0 0 8px', whiteSpace: 'pre-wrap' }}>{r.review}</p>
                          <div className="small muted">
                            id <span className="mono">{r._id.slice(0, 12)}</span> · {r.review_length} words · quarter {r.quarter_label || 'n/a'} ·
                            label source {r.sentiment_source || 'none'} · dataset {r.dataset_id}
                          </div>
                        </td></tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="row between mt">
              <div className="row small muted">
                Rows per page
                <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1) }} aria-label="Rows per page">
                  {[10, 20, 50, 100].map((n) => <option key={n}>{n}</option>)}
                </select>
              </div>
              <div className="row">
                <span className="small muted">Page {data.page} of {Math.max(1, data.pages)}</span>
                <button className="btn sm" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft size={15} /></button>
                <button className="btn sm" disabled={page >= data.pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight size={15} /></button>
              </div>
            </div>
          </>
        )}
      </Card>
    </>
  )
}
