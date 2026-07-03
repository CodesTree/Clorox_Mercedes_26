"""Train + evaluate the resale-value model; dump model.joblib + metrics.json.

Mirrors 03_modeling.ipynb. Run end-to-end from backend/:  python -m ml.train
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.config import get_settings
from ml import ingest, metrics

ARTIFACTS_DIR = Path(__file__).resolve().parents[0] / "artifacts"

CATEGORICAL = ["model", "transmission", "fuel_type"]
NUMERIC = ["age", "mileage", "engine_size", "mpg", "tax", "battery_soh", "trans_adapt_offset"]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "price_rm"
GROUP = "model"
RANDOM_STATE = 42

# Prediction-interval band (spec: ~92% via tree spread); Gate 2 validates coverage.
INTERVAL_LOW_PCT = 4.0
INTERVAL_HIGH_PCT = 96.0


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CATEGORICAL),
            ("num", StandardScaler(), NUMERIC),
        ]
    )


def build_rf(n_estimators: int = 300) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=20,
        min_samples_leaf=2,
        max_features="sqrt",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def make_pipeline(estimator) -> Pipeline:
    return Pipeline([("prep", build_preprocessor()), ("model", estimator)])


def iter_group_folds(df: pd.DataFrame, n_splits: int = 5):
    """Yield (train_idx, val_idx) so a `model` never spans a fold's train/val."""
    gkf = GroupKFold(n_splits=n_splits)
    yield from gkf.split(df[FEATURES], df[TARGET], groups=df[GROUP])


def _aggregate(fold_metrics: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    keys = ["mae", "mape", "rmse", "r2"]
    agg: dict[str, dict[str, float]] = {}
    for k in keys:
        vals = np.array([fm[k] for fm in fold_metrics], dtype=float)
        agg[k] = {"mean": float(np.nanmean(vals)), "std": float(np.nanstd(vals))}
    return agg


def evaluate(df: pd.DataFrame, n_splits: int = 5, n_estimators: int = 300) -> dict:
    """Per-fold + aggregate MAE/MAPE/RMSE/R² for RF and LR under GroupKFold."""
    estimators = {
        "random_forest": lambda: build_rf(n_estimators=n_estimators),
        "linear_regression": lambda: LinearRegression(),
    }
    report: dict = {}
    folds = list(iter_group_folds(df, n_splits=n_splits))
    for name, factory in estimators.items():
        fold_metrics = []
        for train_idx, val_idx in folds:
            pipe = make_pipeline(factory())
            pipe.fit(df.iloc[train_idx][FEATURES], df.iloc[train_idx][TARGET])
            preds = pipe.predict(df.iloc[val_idx][FEATURES])
            fold_metrics.append(metrics.evaluate_metrics(df.iloc[val_idx][TARGET], preds))
        report[name] = {"folds": fold_metrics, "aggregate": _aggregate(fold_metrics)}
    return report


def _empirical_interval_coverage(df: pd.DataFrame, n_splits: int, n_estimators: int) -> dict:
    """Fraction of held-out targets that fall inside the per-tree percentile band."""
    inside = 0
    total = 0
    for train_idx, val_idx in iter_group_folds(df, n_splits=n_splits):
        pipe = make_pipeline(build_rf(n_estimators=n_estimators))
        pipe.fit(df.iloc[train_idx][FEATURES], df.iloc[train_idx][TARGET])
        prep, rf = pipe.named_steps["prep"], pipe.named_steps["model"]
        Xt = prep.transform(df.iloc[val_idx][FEATURES])
        per_tree = np.stack([est.predict(Xt) for est in rf.estimators_])  # (trees, rows)
        low = np.percentile(per_tree, INTERVAL_LOW_PCT, axis=0)
        high = np.percentile(per_tree, INTERVAL_HIGH_PCT, axis=0)
        y = df.iloc[val_idx][TARGET].to_numpy()
        inside += int(np.sum((y >= low) & (y <= high)))
        total += len(y)
    return {
        "low_pct": INTERVAL_LOW_PCT,
        "high_pct": INTERVAL_HIGH_PCT,
        "nominal_coverage": (INTERVAL_HIGH_PCT - INTERVAL_LOW_PCT) / 100.0,
        "empirical_coverage": (inside / total) if total else float("nan"),
    }


def main(
    df: pd.DataFrame | None = None,
    artifacts_dir: Path = ARTIFACTS_DIR,
    n_splits: int = 5,
    n_estimators: int = 300,
) -> dict:
    """Evaluate, fit the production RF on all rows, and write both artifacts."""
    settings = get_settings()
    if df is None:
        df = ingest.build_engineered_csv()

    report = evaluate(df, n_splits=n_splits, n_estimators=n_estimators)
    interval = _empirical_interval_coverage(df, n_splits=n_splits, n_estimators=n_estimators)

    production = make_pipeline(build_rf(n_estimators=n_estimators))
    production.fit(df[FEATURES], df[TARGET])

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(production, artifacts_dir / "model.joblib")

    meta = {
        "models": report,
        "interval": interval,
        "features": FEATURES,
        "categorical": CATEGORICAL,
        "numeric": NUMERIC,
        "target": TARGET,
        "group": GROUP,
        "rf_params": production.named_steps["model"].get_params(),
        "mape_floor_rm": metrics.MAPE_FLOOR_RM,
        "fx_gbp_to_rm": settings.fx_gbp_to_rm,
        "n_rows": int(len(df)),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Prices are UK levels converted to RM via FX_GBP_TO_RM. "
                 "battery_soh and trans_adapt_offset are simulated OBD-II features.",
    }
    (artifacts_dir / "metrics.json").write_text(json.dumps(meta, indent=2, default=str))
    return meta


if __name__ == "__main__":
    result = main()
    rf = result["models"]["random_forest"]["aggregate"]
    lr = result["models"]["linear_regression"]["aggregate"]
    print(f"RF  MAE={rf['mae']['mean']:.0f}  MAPE={rf['mape']['mean']:.2f}%  R2={rf['r2']['mean']:.3f}")
    print(f"LR  MAE={lr['mae']['mean']:.0f}  MAPE={lr['mape']['mean']:.2f}%  R2={lr['r2']['mean']:.3f}")
    print(f"interval empirical coverage: {result['interval']['empirical_coverage']:.3f}")
