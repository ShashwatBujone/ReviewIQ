import { Card } from '../components/ui'

const STEPS = [
  ['Extract', 'CSV files are uploaded, decoded (UTF-8 / Windows-1252), and profiled: row counts, missing values, invalid ratings, unparseable dates and duplicates.'],
  ['Transform', 'Columns are mapped to logical fields, text is cleaned, dates are split into year / quarter / month, ratings are validated, labels are normalised (or derived from ratings), surrogate keys are generated and duplicates are removed.'],
  ['Load', 'Fact documents are inserted into fact_reviews (duplicates already in the warehouse are skipped) and the product, brand, date and sentiment dimensions are rebuilt.'],
  ['Pre-process', 'Lower-casing, contraction expansion (don’t → do not), removal of URLs, HTML, e-mails, digits and punctuation, and stop-word removal that deliberately keeps negations such as “not” and “never”.'],
  ['Vectorise', 'TF-IDF with unigrams and bigrams, sub-linear term frequency and min_df = 2. The vectoriser is fitted on the training split only, so no test information leaks into the features.'],
  ['Train & evaluate', 'Stratified train/test split, Logistic Regression and Multinomial Naive Bayes with class re-weighting, k-fold cross-validation, and accuracy, precision, recall, F1 and confusion matrices on the held-out test set.'],
  ['Serve', 'The fitted vectoriser and both models are saved with joblib, loaded when the API starts, and used for single and batch predictions.'],
  ['Analyse', 'MongoDB aggregation pipelines power the dashboard, the insight charts and the OLAP roll-up, drill-down, slice and dice operations.'],
]

export default function About() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>About ReviewIQ</h1>
          <p>Customer Review Sentiment Analysis and Data Warehouse Analytics — a Data Warehousing &amp; Mining project combining an ETL pipeline, a logical star schema, OLAP analytics and supervised text classification.</p>
        </div>
      </div>

      <div className="grid g2">
        <Card title="Objectives">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>Build an ETL pipeline that turns raw review CSVs into a clean, de-duplicated warehouse.</li>
            <li>Model the warehouse as a star schema (FactReview with Product, Brand, Date and Sentiment dimensions).</li>
            <li>Provide OLAP operations — roll-up, drill-down, slice and dice — over the review cube.</li>
            <li>Train and compare two classic text classifiers for positive / neutral / negative sentiment.</li>
            <li>Present the results in an honest, interactive dashboard where every figure comes from real data.</li>
          </ul>
        </Card>
        <Card title="Technology stack">
          <dl className="kv">
            <dt>Frontend</dt><dd>React 18, Vite, React Router, Recharts, Lucide icons, hand-written CSS</dd>
            <dt>Backend</dt><dd>Python, FastAPI (Swagger docs at /docs), Uvicorn, Pydantic</dd>
            <dt>Machine learning</dt><dd>scikit-learn (TfidfVectorizer, LogisticRegression, MultinomialNB), pandas, NumPy, joblib</dd>
            <dt>Database</dt><dd>MongoDB via PyMongo (local or Atlas); optional in-memory demo store (mongomock)</dd>
            <dt>Data exchange</dt><dd>CSV upload, CSV export of reviews, predictions and metrics, batch prediction</dd>
          </dl>
        </Card>
      </div>

      <Card title="Methodology" className="mt">
        <div className="grid g4">
          {STEPS.map(([t, d], i) => (
            <div key={t} className="card" style={{ padding: 14, background: 'var(--surface-2)' }}>
              <div className="small" style={{ color: 'var(--accent)', fontWeight: 700 }}>{String(i + 1).padStart(2, '0')}</div>
              <strong>{t}</strong>
              <p className="small" style={{ margin: '4px 0 0', color: 'var(--text-2)' }}>{d}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid g3 mt">
        <Card title="TF-IDF">
          <p className="small" style={{ marginTop: 0 }}>Each review becomes a sparse vector. A term’s weight grows with how often it appears in the review and shrinks the more reviews contain it:</p>
          <pre className="code">{'tfidf(t, d) = (1 + log tf(t, d)) × idf(t)\nidf(t) = ln((1 + N) / (1 + df(t))) + 1'}</pre>
          <p className="small">Vectors are L2-normalised, so long and short reviews are comparable.</p>
        </Card>
        <Card title="Logistic Regression">
          <p className="small" style={{ marginTop: 0 }}>A discriminative linear model. For three classes it learns one weight per term per class and turns the scores into probabilities with the softmax function:</p>
          <pre className="code">{'P(y = k | x) = exp(w_k·x + b_k) / Σ_j exp(w_j·x + b_j)'}</pre>
          <p className="small">L2 regularisation (parameter C) limits over-fitting; class_weight = "balanced" counters class imbalance.</p>
        </Card>
        <Card title="Multinomial Naive Bayes">
          <p className="small" style={{ marginTop: 0 }}>A generative model that assumes terms are conditionally independent given the class:</p>
          <pre className="code">{'P(k | d) ∝ P(k) × Π_t P(t | k)^x_t\nP(t | k) = (count(t,k) + α) / (Σ count(·,k) + α|V|)'}</pre>
          <p className="small">α is Laplace/Lidstone smoothing. It trains extremely fast and is a strong baseline for text.</p>
        </Card>
      </div>

      <Card title="Honest-reporting principles" className="mt">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>No metric, total or prediction is hard-coded — all are computed from the stored data or the trained models.</li>
          <li>Labels derived from star ratings are clearly marked as rating-derived; they are a proxy for sentiment, not verified annotations. Rows with missing or invalid labels are excluded from training.</li>
          <li>Because positive reviews dominate, accuracy is always shown next to the majority-class baseline, and the best model is chosen by macro F1.</li>
          <li>Duplicate texts are removed before splitting so the same review cannot appear in both training and test sets.</li>
          <li>The star schema is a logical design implemented with MongoDB documents and aggregation pipelines — MongoDB is not a relational database.</li>
          <li>When MongoDB is unavailable, the optional demo mode says plainly that data is held in memory and not persisted.</li>
        </ul>
      </Card>
    </>
  )
}
