import json

import numpy as np
import pandas as pd

from ml import train


def _engineered_frame(n_per_model: int = 8) -> pd.DataFrame:
    """A small engineered-shape frame with several `model` groups."""
    rng = np.random.default_rng(0)
    models = ["A Class", "C Class", "E Class", "S Class", "GLC", "SLK"]
    rows = []
    for i, m in enumerate(models):
        for _ in range(n_per_model):
            age = int(rng.integers(1, 15))
            mileage = int(rng.integers(5_000, 150_000))
            rows.append(
                {
                    "model": m,
                    "year": 2026 - age,
                    "age": age,
                    "mileage": mileage,
                    "transmission": rng.choice(["Automatic", "Manual", "Semi-Auto"]),
                    "fuel_type": rng.choice(["Petrol", "Diesel", "Hybrid"]),
                    "engine_size": float(rng.choice([1.6, 2.0, 3.0])),
                    "mpg": float(rng.uniform(30, 65)),
                    "tax": float(rng.choice([20, 150, 325, 555])),
                    "battery_soh": float(rng.uniform(40, 100)),
                    "trans_adapt_offset": float(-rng.uniform(0.0, 0.12)),
                    # price loosely tied to age/mileage so the model has signal
                    "price_rm": int(300_000 - age * 8_000 - mileage * 0.4 + i * 5_000),
                }
            )
    return pd.DataFrame(rows)


def test_group_folds_never_leak_a_model_across_train_val():
    df = _engineered_frame()
    for train_idx, val_idx in train.iter_group_folds(df, n_splits=3):
        train_models = set(df.iloc[train_idx]["model"])
        val_models = set(df.iloc[val_idx]["model"])
        assert train_models.isdisjoint(val_models)


def test_evaluate_returns_both_models_and_four_metrics():
    df = _engineered_frame()
    report = train.evaluate(df, n_splits=3, n_estimators=25)
    assert set(report) == {"random_forest", "linear_regression"}
    for model_report in report.values():
        assert "folds" in model_report and "aggregate" in model_report
        assert set(model_report["aggregate"]) == {"mae", "mape", "rmse", "r2"}
        for metric_stats in model_report["aggregate"].values():
            assert set(metric_stats) == {"mean", "std"}


def test_main_writes_model_and_metrics(tmp_path):
    df = _engineered_frame()
    artifacts = tmp_path / "artifacts"
    train.main(df=df, artifacts_dir=artifacts, n_splits=3, n_estimators=25)
    model_path = artifacts / "model.joblib"
    metrics_path = artifacts / "metrics.json"
    assert model_path.exists() and metrics_path.exists()

    meta = json.loads(metrics_path.read_text())
    assert meta["n_rows"] == len(df)
    assert meta["features"]  # non-empty feature list
    assert "fx_gbp_to_rm" in meta
    assert "rf_params" in meta
    assert "interval" in meta  # calibrated coverage recorded

    import joblib
    pipe = joblib.load(model_path)
    pred = pipe.predict(df.head(1))
    assert pred.shape == (1,)
