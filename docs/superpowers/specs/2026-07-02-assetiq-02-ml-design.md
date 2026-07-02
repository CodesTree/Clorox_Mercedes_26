# AssetIQ — Phase 02: ML Model

**Track:** ML
**Depends on:** 00 (`training_data` schema). Can run before the scraper exists — trains on
`training_data` only.
**Gate:** ⛔ **Gate 2** — RF-vs-LR metrics review before the model powers the dashboard.

## Objective

Train a resale-value model on `training_data` (RM), evaluate it honestly, and serialise an artifact
plus a predictor interface the backend consumes.

## Consumes

- `training_data` (populated by Phase 01 ingest; ML may also read a cleaned `merc.csv` directly if
  ingest isn't merged yet, using the same cleaning contract).

## Produces

- `backend/ml/artifacts/model.joblib` — a fitted sklearn `Pipeline` (production RF).
- `backend/ml/artifacts/metrics.json` — full evaluation results.
- **Predictor interface** (contract for Phase 03): `predict(profile: dict) -> {value_rm, low_rm,
  high_rm, confidence}` and `depreciation(profile, years) -> [{year, value_rm, retained_pct}]`.

## Features & target

- Target: `price_rm`.
- Features: `model` (categorical), `age` (= current_year − year), `mileage`, `transmission` (cat),
  `fuel_type` (cat), `engine_size`, `mpg`, `tax`.
- `mpg` and `tax` are **UK-origin** numerics; kept as features but documented as UK-derived.
- Preprocessing: `ColumnTransformer` — OneHotEncoder(handle_unknown="ignore") for categoricals,
  passthrough/scaler for numerics. Same preprocessor feeds both models.

## Models (`ml/train.py`)

- **Production:** `RandomForestRegressor` (seeded; sensible n_estimators/max_depth, lightly tuned).
- **Baseline:** `LinearRegression` on the same preprocessed features.

## Evaluation

- **`GroupKFold(groups=model)`** so a class never appears in both train and validation of a fold.
- Metrics per fold **and** aggregated (mean ± std): **MAE, MAPE, RMSE, R²** — for **both** models.
- `metrics.json` holds the per-fold table + aggregates + feature list + FX rate used + row count +
  training timestamp.

## Prediction interval (the mockup's "92% confidence")

From the fitted RF, collect per-tree predictions for the input; report `value_rm` = ensemble mean,
`[low_rm, high_rm]` = the central interval from the tree spread (e.g. 4th–96th percentile ≈ 92%),
`confidence` = the nominal coverage. Documented as ensemble-derived, not invented.

## Depreciation curve (the mockup's retained-value line)

Hold the profile fixed, advance `age` forward N years, predict `value_rm` at each step;
`retained_pct = value_at_year / value_today`. Purely model-derived.

## ⛔ Gate 2 — what I bring to you

The metrics table (RF vs LR, per-fold and aggregate MAE/MAPE/RMSE/R²), plus the interval method and
a couple of sanity predictions. We agree it's good enough **before** it's wired into the dashboard.

## Tests (PyTest)

- Training smoke on a small sampled frame produces a fitted pipeline + `metrics.json`.
- Metric functions match hand-computed values on a tiny fixture.
- `GroupKFold` never leaks a `model` across a fold's train/val split.
- `predict` returns `low_rm ≤ value_rm ≤ high_rm`, all positive.
- `depreciation` is monotonically non-increasing over increasing age.
- Unknown categorical value doesn't crash (handle_unknown ignore).

## Done criteria

- `python -m ml.train` writes `model.joblib` + `metrics.json`.
- Predictor interface importable and returns the documented shapes.
- Gate-2 metrics reviewed and approved before Phase 03 depends on the real artifact.
- Caveat restated in `metrics.json` notes: prices are UK levels in RM via `FX_GBP_TO_RM`.
