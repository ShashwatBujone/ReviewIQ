import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Analyzer from './pages/Analyzer'
import Reviews from './pages/Reviews'
import Datasets from './pages/Datasets'
import Models from './pages/Models'
import Insights from './pages/Insights'
import WarehousePage from './pages/Warehouse'
import About from './pages/About'
import './styles.css'

function NotFound() {
  return <div className="empty"><h4>Page not found</h4><a href="/">Back to the dashboard</a></div>
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analyzer" element={<Analyzer />} />
          <Route path="/reviews" element={<Reviews />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="/models" element={<Models />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/warehouse" element={<WarehousePage />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  </React.StrictMode>,
)
