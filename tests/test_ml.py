import numpy as np
import pytest

from services.ml import ModelService, TrainingError
from services.preprocessing import model_input_text

PARAMS = dict(test_size=0.2, random_state=42, include_title=True, deduplicate=True, balance_classes=True,
              max_features=20000, ngram_max=2, lr_C=1.0, nb_alpha=0.1, cv_folds=3)


def _data(df):
    texts = [model_input_text(t, r) for t, r in zip(df["review_title"], df["review"])]
    return texts, df["sentiment"].tolist()


def test_train_evaluate_save_load(sample_df, tmp_path):
    svc = ModelService(tmp_path)
    texts, labels = _data(sample_df)
    meta = svc.train(texts, labels, PARAMS, {"source": "test"})
    d = meta["data"]
    assert d["train_size"] + d["test_size"] == d["used_for_training"]
    assert d["used_for_training"] + d["dropped_duplicate_texts"] == len(sample_df)
    for key, r in meta["results"].items():
        for m in ["accuracy", "precision_macro", "recall_macro", "f1_macro", "f1_weighted"]:
            assert 0.0 <= r[m] <= 1.0
        cm = np.array(r["confusion_matrix"]["matrix"])
        assert cm.sum() == d["test_size"]
        assert np.isclose(np.trace(cm) / cm.sum(), r["accuracy"], atol=1e-4)
        assert set(r["per_class"]) == {"negative", "neutral", "positive"}
        assert "cv_f1_macro_mean" in r
    assert meta["best_model"] in meta["results"]
    assert meta["selection_metric"] == "cv_f1_macro_mean"
    assert 0 < meta["baseline"]["accuracy"] < 1

    # Round-trip: a freshly loaded service gives identical predictions.
    text = "Stopped working after a week, total waste of money"
    before = svc.predict(text)
    svc2 = ModelService(tmp_path)
    assert svc2.load() and svc2.ready
    assert svc2.predict(text)["predictions"] == before["predictions"]
    for p in before["predictions"].values():
        assert abs(sum(p["probabilities"].values()) - 1) < 1e-3
        assert p["confidence"] == max(p["probabilities"].values())


def test_predict_unknown_words_warns(sample_df, tmp_path):
    svc = ModelService(tmp_path)
    svc.train(*_data(sample_df), PARAMS, {})
    out = svc.predict("zzzz qqqq")
    assert out["known_terms"] == 0 and out["warning"]
    with pytest.raises(ValueError):
        svc.predict("!!! 123 ...")


def test_training_requires_two_classes(tmp_path):
    with pytest.raises(TrainingError):
        ModelService(tmp_path).train(["good one", "great one", "nice"], ["positive"] * 3, PARAMS, {})


def test_untrained_service(tmp_path):
    svc = ModelService(tmp_path)
    assert not svc.load()
    with pytest.raises(TrainingError):
        svc.predict("hello")
