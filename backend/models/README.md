# Saved models

These files are produced by training (the **Train & evaluate** button, `POST /api/models/train`,
or `python train_models.py`) and are loaded automatically when the backend starts.

| File | Contents |
|------|----------|
| `tfidf_vectorizer.joblib` | Fitted TF-IDF vectoriser (vocabulary + IDF weights) |
| `logistic_regression.joblib` | Fitted Logistic Regression |
| `naive_bayes.joblib` | Fitted Multinomial Naive Bayes |
| `model_metadata.json` | Parameters, data summary, test-set metrics, confusion matrices, CV scores, baseline |

The copies shipped in the ZIP were trained on `data/sample/customer_reviews_preprocessed.csv`
with the default settings. If your scikit-learn version differs, the app shows a notice — just retrain.
Delete these files to start without trained models.
