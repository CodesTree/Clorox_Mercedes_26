import json

import numpy as np
import pandas as pd

from ml import train


def _engineered_frame(n_per_model: int = 8) -> pd.DataFrame:
    """A small pooled-engineered-shape frame with several `model_class` groups."""
    rng = np.random.default_rng(0)
    classes = ["A", "C", "E", "S", "GLC", "SLK"]
    markets = ["uk", "germany", "us"]
    rows = []
    for i, mc in enumerate(classes):
        for _ in range(n_per_model):
            age = int(rng.integers(1, 15))
            mileage = int(rng.integers(5_000, 200_000))
            rows.append({
                "model_class": mc,
                "source_market": rng.choice(markets),
                "year": 2026 - age,
                "age": age,
                "mileage": mileage,
                "transmission": rng.choice(["Automatic", "Manual", "Semi-Auto"]),
                "fuel_type": rng.choice(["Petrol", "Diesel", "Hybrid"]),
                "engine_size": float(rng.choice([1.6, 2.0, 3.0])),
                "battery_soh": float(rng.uniform(40, 100)),
                "trans_adapt_offset": float(-rng.uniform(0.0, 0.12)),
                # enriched specs (some nullable to exercise the imputer)
                "engine_config": rng.choice(["L4", "V6", "V8"]),
                "aspiration": rng.choice(["turbo", "naturally_aspirated"]),
                "gear_type": rng.choice(["automatic", "manual"]),
                "front_brake": rng.choice(["Ventilated Discs", "Discs"]),
                "rear_brake": rng.choice(["Ventilated Discs", "Discs"]),
                "n_cylinders": float(rng.choice([4, 6, 8])),
                "n_gears": float(rng.choice([6, 7, 9])),
                "top_speed_kmh": float(rng.uniform(200, 260)),
                "torque_nm": float(rng.uniform(250, 700)),
                "accel_0_100_s": float(rng.uniform(4.5, 9.5)),
                "boot_l": float(rng.choice([np.nan, 400, 500, 600])),
                # price loosely tied to age/mileage so the model has signal
                "price_rm": int(300_000 - age * 8_000 - mileage * 0.4 + i * 5_000),
            })
    return pd.DataFrame(rows)


def test_group_folds_never_leak_a_model_class_across_train_val():
    df = _engineered_frame()
    for train_idx, val_idx in train.iter_group_folds(df, n_splits=3):
        train_classes = set(df.iloc[train_idx]["model_class"])
        val_classes = set(df.iloc[val_idx]["model_class"])
        assert train_classes.isdisjoint(val_classes)


def test_evaluate_returns_both_models_and_four_metrics():
    df = _engineered_frame()
    report = train.evaluate(df, n_splits=3, n_estimators=25)
    assert set(report) == {"random_forest", "ridge"}
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
    assert "fx_rates" in meta and "eur_to_rm" in meta["fx_rates"]
    assert "source_markets" in meta
    assert "rf_params" in meta
    assert "interval" in meta  # calibrated coverage recorded

    import joblib
    pipe = joblib.load(model_path)
    pred = pipe.predict(df.head(1))
    assert pred.shape == (1,)


def test_onehot_avoids_dummy_variable_trap():
    # With an intercept column the design matrix must stay full rank, or the
    # LinearRegression baseline explodes (dummy-variable trap). drop='first' fixes it.
    df = _engineered_frame()
    prep = train.build_preprocessor()
    Xt = prep.fit_transform(df[train.FEATURES])
    Xt = np.asarray(Xt.todense()) if hasattr(Xt, "todense") else np.asarray(Xt)
    design = np.hstack([np.ones((Xt.shape[0], 1)), Xt])
    assert np.linalg.matrix_rank(design) == design.shape[1]


def test_numeric_imputer_handles_null_specs():
    # boot_l has NaNs; the pipeline must not propagate them into the fitted model.
    df = _engineered_frame()
    prep = train.build_preprocessor()
    Xt = prep.fit_transform(df[train.FEATURES])
    Xt = np.asarray(Xt.todense()) if hasattr(Xt, "todense") else np.asarray(Xt)
    assert not np.isnan(Xt).any()
