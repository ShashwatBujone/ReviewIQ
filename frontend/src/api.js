// Backend URL is configurable through VITE_API_URL (see frontend/.env.example)
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

function buildUrl(path, params) {
  const url = new URL(API_URL + path)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return
      if (Array.isArray(v)) v.forEach((x) => x !== '' && x != null && url.searchParams.append(k, x))
      else url.searchParams.append(k, v)
    })
  }
  return url.toString()
}

function errorMessage(body, status) {
  const d = body && body.detail
  if (Array.isArray(d)) return d.map((e) => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ')
  if (typeof d === 'string') return d
  return `Request failed with status ${status}`
}

export async function request(path, { method = 'GET', body, form, params } = {}) {
  let res
  try {
    res = await fetch(buildUrl(path, params), {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : form,
    })
  } catch {
    throw new Error(`Cannot reach the backend at ${API_URL}. Make sure it is running (start-backend.bat).`)
  }
  const type = res.headers.get('content-type') || ''
  const data = type.includes('application/json') ? await res.json().catch(() => null) : await res.blob()
  if (!res.ok) {
    const err = new Error(errorMessage(data, res.status))
    err.status = res.status
    throw err
  }
  return data
}

export const fileUrl = (path, params) => buildUrl(path, params)

export function saveBlob(blob, filename) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

export const api = {
  health: () => request('/api/health'),
  reconnect: () => request('/api/health/reconnect', { method: 'POST' }),
  dashboard: () => request('/api/dashboard/stats'),
  analytics: (params) => request('/api/analytics/summary', { params }),
  reviews: (params) => request('/api/reviews', { params }),
  filterOptions: () => request('/api/reviews/filters'),

  datasets: () => request('/api/datasets'),
  dataset: (id) => request(`/api/datasets/${id}`),
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/datasets/upload', { method: 'POST', form })
  },
  validate: (id, body) => request(`/api/datasets/${id}/validate`, { method: 'POST', body }),
  importDataset: (id, body) => request(`/api/datasets/${id}/import`, { method: 'POST', body }),
  importSample: (mode = 'append') => request('/api/datasets/sample/import', { method: 'POST', params: { mode } }),
  deleteDataset: (id) => request(`/api/datasets/${id}`, { method: 'DELETE' }),
  resetWarehouse: () => request('/api/warehouse/reset', { method: 'POST', params: { confirm: true } }),

  modelStatus: () => request('/api/models/status'),
  train: (body) => request('/api/models/train', { method: 'POST', body }),
  modelRuns: () => request('/api/models/runs'),
  predict: (body) => request('/api/predict', { method: 'POST', body }),
  predictBatch: (file, model, textColumn) => {
    const form = new FormData()
    form.append('file', file)
    form.append('model', model)
    if (textColumn) form.append('text_column', textColumn)
    return request('/api/predict/batch', { method: 'POST', form })
  },
  predictionHistory: () => request('/api/predict/history', { params: { limit: 15 } }),

  schema: () => request('/api/warehouse/schema'),
  etlRuns: () => request('/api/warehouse/etl-runs'),
  rollup: (params) => request('/api/warehouse/olap/rollup', { params }),
  drilldown: (params) => request('/api/warehouse/olap/drilldown', { params }),
  slice: (body) => request('/api/warehouse/olap/slice', { method: 'POST', body }),
  dice: (body) => request('/api/warehouse/olap/dice', { method: 'POST', body }),
  cube: (body) => request('/api/warehouse/cube', { method: 'POST', body }),
}
