"""Model training, evaluation, persistence and inference.

TF-IDF features + Logistic Regression and Multinomial Naive Bayes. All metrics returned
here are computed from a held-out test split; nothing is hard-coded.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_recall_fscore_support)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.utils.class_weight import compute_sample_weight

from services.preprocessing import LABELS, clean_text

log = logging.getLogger("reviewiq.ml")

MODEL_NAMES = {"logistic_regression": "Logistic Regression", "naive_bayes": "Multinomial Naive Bayes"}
ARTIFACTS = {"vectorizer": "tfidf_vectorizer.joblib", "logistic_regression": "logistic_regression.joblib",
             "naive_bayes": "naive_bayes.joblib", "metadata": "model_metadata.json"}


class TrainingError(ValueError):
    pass


def _make_vectorizer(params: dict, min_df: int) -> TfidfVectorizer:
    return TfidfVectorizer(ngram_range=(1, params["ngram_max"]), min_df=min_df,
                           max_features=params["max_features"], sublinear_tf=True)


def _make_models(params: dict) -> dict:
    return {
        "logistic_regression": LogisticRegression(
            C=params["lr_C"], max_iter=3000,
            class_weight="balanced" if params["balance_classes"] else None),
        "naive_bayes": MultinomialNB(alpha=params["nb_alpha"]),
    }


def _fit(name: str, model, X, y, balance: bool):
    if name == "naive_bayes" and balance:
        # MultinomialNB has no class_weight; balanced sample weights give the same effect.
        model.fit(X, y, sample_weight=compute_sample_weight("balanced", y))
    else:
        model.fit(X, y)
    return model


def _evaluate(model, X_test, y_test, labels: list[str]) -> dict:
    y_pred = model.predict(X_test)
    p_mac, r_mac, f_mac, _ = precision_recall_fscore_support(y_test, y_pred, labels=labels, average="macro", zero_division=0)
    p_w, r_w, f_w, _ = precision_recall_fscore_support(y_test, y_pred, labels=labels, average="weighted", zero_division=0)
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision_macro": round(float(p_mac), 4), "recall_macro": round(float(r_mac), 4),
        "f1_macro": round(float(f_mac), 4),
        "precision_weighted": round(float(p_w), 4), "recall_weighted": round(float(r_w), 4),
        "f1_weighted": round(float(f_w), 4),
        "per_class": {lab: {"precision": round(report[lab]["precision"], 4), "recall": round(report[lab]["recall"], 4),
                            "f1": round(report[lab]["f1-score"], 4), "support": int(report[lab]["support"])}
                      for lab in labels},
        "confusion_matrix": {"labels": labels,
                             "matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist()},
    }


def _top_features(name: str, model, vocab: np.ndarray, n: int = 12) -> dict:
    out = {}
    if name == "logistic_regression":
        coefs = model.coef_
        if coefs.shape[0] == 1:  # binary case: one row of coefficients
            coefs = np.vstack([-coefs[0], coefs[0]])
        for i, lab in enumerate(model.classes_):
            idx = np.argsort(coefs[i])[::-1][:n]
            out[lab] = [{"term": vocab[j], "weight": round(float(coefs[i][j]), 4)} for j in idx]
    else:
        logp = model.feature_log_prob_
        for i, lab in enumerate(model.classes_):
            score = logp[i] - np.delete(logp, i, axis=0).mean(axis=0)
            idx = np.argsort(score)[::-1][:n]
            out[lab] = [{"term": vocab[j], "weight": round(float(score[j]), 4)} for j in idx]
    return out


class ModelService:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        self.vectorizer = None
        self.models: dict = {}
        self.metadata: dict | None = None
        self.load_error: str | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ persistence
    @property
    def ready(self) -> bool:
        return self.vectorizer is not None and len(self.models) == 2

    def load(self) -> bool:
        paths = {k: self.model_dir / v for k, v in ARTIFACTS.items()}
        if not all(p.exists() for p in paths.values()):
            self.load_error = "No saved models found. Train the models first."
            return False
        try:
            self.vectorizer = joblib.load(paths["vectorizer"])
            self.models = {k: joblib.load(paths[k]) for k in MODEL_NAMES}
            self.metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
            self.load_error = None
            saved_ver = self.metadata.get("sklearn_version")
            if saved_ver and saved_ver != sklearn.__version__:
                self.load_error = (f"Models were saved with scikit-learn {saved_ver} but {sklearn.__version__} is "
                                   "installed. They loaded, but retraining is recommended.")
            log.info("Loaded saved models from %s", self.model_dir)
            return True
        except Exception as exc:  # corrupted / incompatible pickle
            self.vectorizer, self.models, self.metadata = None, {}, None
            self.load_error = f"Saved models could not be loaded ({type(exc).__name__}: {exc}). Please retrain."
            log.warning(self.load_error)
            return False

    def _save(self) -> None:
        self.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.vectorizer, self.model_dir / ARTIFACTS["vectorizer"])
        for k in MODEL_NAMES:
            joblib.dump(self.models[k], self.model_dir / ARTIFACTS[k])
        (self.model_dir / ARTIFACTS["metadata"]).write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ training
    def train(self, texts: list[str], labels: list[str], params: dict, data_summary: dict) -> dict:
        """texts must already be cleaned with clean_text / model_input_text."""
        with self._lock:
            return self._train(texts, labels, params, data_summary)

    def _train(self, texts, labels, params, data_summary) -> dict:
        texts = np.asarray(texts, dtype=object)
        y = np.asarray(labels, dtype=object)
        keep = np.array([bool(t) for t in texts])
        dropped_empty = int((~keep).sum())
        texts, y = texts[keep], y[keep]

        # Remove exact duplicate texts so identical reviews cannot appear in both train and test.
        dropped_dupes = conflicting = 0
        if params["deduplicate"]:
            seen: dict[str, str] = {}
            mask = np.zeros(len(texts), dtype=bool)
            for i, (t, lab) in enumerate(zip(texts, y)):
                if t in seen:
                    dropped_dupes += 1
                    if seen[t] != lab:
                        conflicting += 1
                    continue
                seen[t] = lab
                mask[i] = True
            texts, y = texts[mask], y[mask]

        classes, counts = np.unique(y, return_counts=True)
        dist = {c: int(n) for c, n in zip(classes, counts)}
        if len(classes) < 2:
            raise TrainingError("At least two sentiment classes are needed to train. Found: " + str(dist))
        if counts.min() < 2:
            raise TrainingError(f"Every class needs at least 2 examples for a stratified split. Found: {dist}")
        n_test_min = len(classes)
        if len(y) * params["test_size"] < n_test_min:
            raise TrainingError(f"Not enough labeled reviews ({len(y)}) for a test split of {params['test_size']}.")

        labels_order = [lab for lab in LABELS if lab in dist]
        X_tr_txt, X_te_txt, y_tr, y_te = train_test_split(
            texts, y, test_size=params["test_size"], random_state=params["random_state"], stratify=y)

        min_df = 2 if len(X_tr_txt) >= 200 else 1
        vec = _make_vectorizer(params, min_df)
        try:
            X_tr = vec.fit_transform(X_tr_txt)
        except ValueError:  # empty vocabulary with min_df=2
            vec = _make_vectorizer(params, 1)
            X_tr = vec.fit_transform(X_tr_txt)
        X_te = vec.transform(X_te_txt)

        models = _make_models(params)
        vocab = vec.get_feature_names_out()
        results = {}
        for name, model in models.items():
            _fit(name, model, X_tr, y_tr, params["balance_classes"])
            results[name] = {"name": MODEL_NAMES[name], **_evaluate(model, X_te, y_te, labels_order),
                             "top_features": _top_features(name, model, vocab)}

        # Stratified k-fold cross-validation on the training split (vectorizer refit per fold).
        folds = int(min(params["cv_folds"], np.unique(y_tr, return_counts=True)[1].min()))
        if folds >= 2:
            skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=params["random_state"])
            scores = {k: [] for k in models}
            for tr_idx, va_idx in skf.split(X_tr_txt, y_tr):
                v = _make_vectorizer(params, 1)
                Xa, Xb = v.fit_transform(X_tr_txt[tr_idx]), v.transform(X_tr_txt[va_idx])
                for name, m in _make_models(params).items():
                    _fit(name, m, Xa, y_tr[tr_idx], params["balance_classes"])
                    scores[name].append(f1_score(y_tr[va_idx], m.predict(Xb), average="macro", zero_division=0))
            for name in models:
                results[name]["cv_f1_macro_mean"] = round(float(np.mean(scores[name])), 4)
                results[name]["cv_f1_macro_std"] = round(float(np.std(scores[name])), 4)
                results[name]["cv_folds"] = folds

        majority = max(dist, key=dist.get)
        baseline_acc = float(np.mean(y_te == majority))
        # Choose the best model WITHOUT looking at the test set: use cross-validated macro F1 on the
        # training split when available; fall back to test macro F1 only if CV is switched off.
        if all("cv_f1_macro_mean" in r for r in results.values()):
            selection_metric = "cv_f1_macro_mean"
            best = max(results, key=lambda k: (results[k]["cv_f1_macro_mean"], -results[k]["cv_f1_macro_std"]))
        else:
            selection_metric = "f1_macro"
            best = max(results, key=lambda k: (results[k]["f1_macro"], results[k]["accuracy"]))

        run_id = uuid.uuid4().hex[:12]
        self.vectorizer, self.models = vec, models
        self.metadata = {
            "run_id": run_id,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "sklearn_version": sklearn.__version__,
            "params": params,
            "labels": labels_order,
            "best_model": best,
            "selection_metric": selection_metric,
            "data": {
                **data_summary,
                "used_for_training": int(len(y)),
                "dropped_empty_after_cleaning": dropped_empty,
                "dropped_duplicate_texts": dropped_dupes,
                "duplicate_texts_with_conflicting_labels": conflicting,
                "class_distribution": dist,
                "train_size": int(len(y_tr)),
                "test_size": int(len(y_te)),
                "test_class_distribution": {c: int((y_te == c).sum()) for c in labels_order},
                "vocabulary_size": int(len(vocab)),
                "tfidf_min_df": int(vec.min_df),
            },
            "baseline": {"strategy": f"always predict '{majority}'", "accuracy": round(baseline_acc, 4),
                         "f1_macro": round(float(f1_score(y_te, [majority] * len(y_te), labels=labels_order,
                                                          average="macro", zero_division=0)), 4)},
            "results": results,
        }
        self._save()
        self.load_error = None
        return self.metadata

    # ------------------------------------------------------------------ inference
    def predict(self, text: str, model: str = "both") -> dict:
        if not self.ready:
            raise TrainingError(self.load_error or "Models are not trained yet.")
        cleaned = clean_text(text)
        if not cleaned:
            raise ValueError("The text contains no meaningful words after cleaning.")
        X = self.vectorizer.transform([cleaned])
        known = int(X.nnz)
        names = list(MODEL_NAMES) if model == "both" else [model]
        preds = {}
        for name in names:
            m = self.models[name]
            proba = m.predict_proba(X)[0]
            order = np.argsort(proba)[::-1]
            preds[name] = {
                "model": MODEL_NAMES[name],
                "label": str(m.classes_[order[0]]),
                "confidence": round(float(proba[order[0]]), 4),
                "probabilities": {str(c): round(float(p), 4) for c, p in zip(m.classes_, proba)},
            }
        warning = None
        if known == 0:
            warning = ("None of the words in this text appear in the training vocabulary, so the "
                       "prediction only reflects the class balance the model learned.")
        return {"cleaned_text": cleaned, "known_terms": known, "predictions": preds,
                "best_model": self.metadata.get("best_model") if self.metadata else None,
                "warning": warning,
                "confidence_note": "Confidence is the model's predicted class probability (predict_proba). "
                                   "It is an estimate, not a calibrated guarantee."}

    def predict_many(self, texts: list[str], model: str) -> list[dict]:
        if not self.ready:
            raise TrainingError(self.load_error or "Models are not trained yet.")
        cleaned = [clean_text(t) for t in texts]
        X = self.vectorizer.transform(cleaned)
        m = self.models[model]
        proba = m.predict_proba(X)
        out = []
        for c, row in zip(cleaned, proba):
            if not c:
                out.append({"label": None, "confidence": None})
                continue
            i = int(np.argmax(row))
            out.append({"label": str(m.classes_[i]), "confidence": round(float(row[i]), 4)})
        return out

    def status(self) -> dict:
        return {"ready": self.ready, "message": self.load_error,
                "model_dir": str(self.model_dir), "metadata": self.metadata}
