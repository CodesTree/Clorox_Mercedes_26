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

- `backend/ml/notebooks/01_eda.ipynb`, `02_cleaning.ipynb`, `03_modeling.ipynb` — committed,
  outputs cleared, the exploration/prototyping trail (see Workflow below).
- `data/merc_engineered.csv` — the cleaned dataset plus the two simulated-OBD-II feature columns
  (`battery_soh`, `trans_adapt_offset`); raw `data/merc.csv` stays pristine.
- `backend/ml/artifacts/model.joblib` — a fitted sklearn `Pipeline` (production RF).
- `backend/ml/artifacts/metrics.json` — full evaluation results.
- **Predictor interface** (contract for Phase 03): `predict(profile: dict) -> {value_rm, low_rm,
  high_rm, confidence}` and `depreciation(profile, years) -> [{year, value_rm, retained_pct}]`.

## Workflow: notebooks → modular scripts

Work happens in two phases that produce the same artifact by different routes:

**Phase A — Jupyter notebooks (exploration & prototyping).** Three notebooks under
`backend/ml/notebooks/`, committed with cell outputs cleared before each commit:
- `01_eda.ipynb` — explore `data/merc.csv`: distributions, nulls, categorical cardinality,
  correlations. Informs the feature list and cleaning decisions below.
- `02_cleaning.ipynb` — apply the cleaning contract (age = current_year − year, GBP→RM via
  `FX_GBP_TO_RM`, null/outlier handling, dedupe), then synthesise the two simulated-OBD-II
  features (`battery_soh`, `trans_adapt_offset` — see Feature engineering below) and write
  `data/merc_engineered.csv`.
- `03_modeling.ipynb` — build the `ColumnTransformer` preprocessing, train RF + LR, run the
  `GroupKFold` evaluation, derive the prediction interval, sanity-check the depreciation curve,
  then `joblib.dump` the fitted pipeline to `model.joblib` and write `metrics.json`. This is
  where the first working artifact and the Gate 2 evidence come from.

Notebooks are exploration and documentation — not part of the tested/executable pipeline, and
never imported by production code.

**Phase B — Modular scripts (production, tested).** Once a notebook run produces a model worth
keeping, the validated logic is ported into self-contained scripts that reproduce the artifact
without ever opening Jupyter again:
- `backend/ml/ingest.py` — cleaning logic from `02_cleaning.ipynb`.
- `backend/ml/train.py` — pipeline/training/evaluation/dump logic from `03_modeling.ipynb`,
  runnable as `python -m ml.train`.
- `backend/ml/predict.py` — the `predict()`/`depreciation()` predictor interface Phase 03 imports.

All PyTest coverage in this spec targets these scripts, not the notebooks.

**Dependencies:** add `pandas`, `numpy`, `scikit-learn`, `joblib`, `jupyter`, `ipykernel`,
`matplotlib`, `seaborn` to `backend/requirements.txt` (none of these exist there yet).

## Features & target

- Target: `price_rm`.
- Features: `model` (categorical), `age` (= current_year − year), `mileage`, `transmission` (cat),
  `fuel_type` (cat), `engine_size`, `mpg`, `tax`, **`battery_soh`** (numeric, engineered),
  **`trans_adapt_offset`** (numeric, engineered).
- `mpg` and `tax` are **UK-origin** numerics; kept as features but documented as UK-derived.
- `battery_soh` and `trans_adapt_offset` are **simulated OBD-II telemetry**, deterministically
  derived from existing columns + seeded noise (see Feature engineering below). They demonstrate how
  live vehicle-health signals would feed the valuation; they are not real sensor readings.
- Preprocessing: `ColumnTransformer` — OneHotEncoder(handle_unknown="ignore") for categoricals,
  passthrough/scaler for numerics (`age`, `mileage`, `engine_size`, `mpg`, `tax`, `battery_soh`,
  `trans_adapt_offset`). Same preprocessor feeds both models.

## Feature engineering (simulated OBD-II)

Two columns are synthesised in the cleaning step (`02_cleaning.ipynb`, ported to `ingest.py`) to
simulate OBD-II vehicle-health telemetry influencing resale value. Both are **deterministic
functions of existing columns plus seeded Gaussian noise** (fixed `numpy` seed, so the engineered
CSV, `metrics.json`, and tests are reproducible). The raw `data/merc.csv` is never mutated; the
augmented dataset is written to `data/merc_engineered.csv`.

### `battery_soh` — Starter Battery State of Health (%)

Every car starts at 100% and degrades from there. Degradation is fuel-type dependent:

- **Petrol / Diesel / Other** — a conventional **12V starter battery** degrades primarily with
  **time (age)**: an exponential decay in `age` with a small additional `mileage` term.
- **Hybrid** — the **high-voltage battery** degrades primarily with **charge cycles (mileage)**,
  and does so **non-linearly**: high-mileage hybrids lose SoH faster than a linear model would
  predict (the marginal drop accelerates through the mid-mileage range).
- A small **Gaussian noise** term (owner-care variance) is added, then the value is clipped to a
  sensible floor (never negative, never above 100).

### `trans_adapt_offset` — Transmission Adaptation Offset (depreciation modifier, ≤ 0)

Models electronic transmission-control-unit (TCU) hydraulic-adaptation wear:

- **Manual** → **exactly `0.0`**. A manual gearbox has no electronic TCU tracking adaptation, so
  there is no signal. `0.0` is a deliberate sentinel: because `transmission` is itself a categorical
  feature (OneHotEncoded), the RF splits Manual into its own branch first, so a manual car's `0.0`
  is never confused with a "perfectly healthy automatic". As a second safeguard, all non-manual
  offsets are **strictly negative**, so the value `0.0` uniquely tags manual even numerically.
- **Automatic / Semi-Auto / Other** (the "not manual → automatic logic" path) → a **negative
  depreciation modifier that scales with mileage**, bucketed into wear bands:
  - **normal** wear (mileage `< 60,000`)
  - **noticeable** wear (`60,000 ≤ mileage < 120,000`)
  - **critical** wear (`mileage ≥ 120,000`)

  Each band sets a base modifier; a continuous within-band mileage term plus seeded noise makes the
  offset monotonically more negative as mileage rises.

## Models (prototyped in `03_modeling.ipynb`, ported to `ml/train.py`)

- **Production:** `RandomForestRegressor` (seeded; sensible n_estimators/max_depth, lightly tuned).
  > **TODO(Gate2):** finalize RF hyperparameters (n_estimators, max_depth, min_samples_leaf, max_features); record the search/rationale in `metrics.json`. Keep `random_state` fixed for reproducibility.
  > **Resolved (P02 impl):** starting point `n_estimators=300, max_depth=20, min_samples_leaf=2, max_features="sqrt", random_state=42` — recorded in `metrics.json.rf_params`. On the full 12,859-row dataset this scores RF MAE≈21,919 RM / MAPE≈15.0% / R²≈0.74 vs the LR baseline MAE≈37,270 / MAPE≈30.8% / R²≈0.43. Gate 2 finalises. (The `OneHotEncoder` uses `drop="first"` so the LR baseline stays numerically stable.)
- **Baseline:** `LinearRegression` on the same preprocessed features.

## Evaluation

- **`GroupKFold(groups=model)`** so a class never appears in both train and validation of a fold.
- Metrics per fold **and** aggregated (mean ± std): **MAE, MAPE, RMSE, R²** — for **both** models.
- `metrics.json` holds the per-fold table + aggregates + feature list + FX rate used + row count +
  training timestamp.

> **TODO(P02):** guard **MAPE** against near-zero target prices (exclude rows below a floor, or use a small epsilon) so a cheap listing can't explode the percentage. Document the choice in `metrics.json`.
> **Resolved (P02 impl):** MAPE excludes rows with `price_rm < 5000` (`metrics.MAPE_FLOOR_RM`), recorded in `metrics.json.mape_floor_rm`.

## Prediction interval (the mockup's "92% confidence")

From the fitted RF, collect per-tree predictions for the input; report `value_rm` = ensemble mean,
`[low_rm, high_rm]` = the central interval from the tree spread (e.g. 4th–96th percentile ≈ 92%),
`confidence` = the nominal coverage. Documented as ensemble-derived, not invented.

> **TODO(Gate2):** empirically validate that the chosen tree-spread percentiles actually achieve ≈92% coverage on the validation folds; adjust the percentile band if not. Confirm `low_rm ≥ 0`.
> **Resolved (P02 impl):** the 4th–96th-percentile per-tree band (nominal 0.92) achieves **empirical coverage ≈0.867** on the held-out GroupKFold folds — recorded in `metrics.json.interval`. Gate 2 decides whether to widen the band to hit 0.92. `predict()` floors `low_rm` at 0 and clamps so `low_rm ≤ value_rm ≤ high_rm` by construction.

## Depreciation curve (the mockup's retained-value line)

Hold the profile fixed, advance `age` forward N years, predict `value_rm` at each step;
`retained_pct = value_at_year / value_today`. Purely model-derived.

> **TODO(P02):** set the max forecast horizon (e.g. 5–7 years) and a non-negative value floor; decide behaviour when advancing `age` pushes a class outside the training age range (clamp vs. extrapolate-with-warning).
> **Resolved (P02 impl):** default horizon 5 years (caller-configurable via `depreciation(profile, years=…)`), value floored at 0, and the curve is forced non-increasing via `np.minimum.accumulate` (RF is not monotonic in `age`). `age` advances with `mileage` held fixed; out-of-range ages simply extrapolate through the RF with the monotonic clamp keeping the curve sane (no hard age cap).

## ⛔ Gate 2 — what I bring to you

The metrics table (RF vs LR, per-fold and aggregate MAE/MAPE/RMSE/R²), plus the interval method and
a couple of sanity predictions — with the three notebooks as the visible paper trail of how the
cleaning and modeling decisions were reached. We agree it's good enough **before** it's wired into
the dashboard.

## Tests (PyTest)

- Notebooks are not directly tested; the scripts they were ported to are (below), and must
  reproduce the artifact independent of ever running the notebooks.
- Training smoke on a small sampled frame produces a fitted pipeline + `metrics.json`.
- Metric functions match hand-computed values on a tiny fixture.
- `GroupKFold` never leaks a `model` across a fold's train/val split.
- `predict` returns `low_rm ≤ value_rm ≤ high_rm`, all positive.
- `depreciation` is monotonically non-increasing over increasing age.
- Unknown categorical value doesn't crash (handle_unknown ignore).
- **Feature engineering:**
  - `battery_soh` for every row is within `(floor, 100]`; a fresh low-mileage car scores high.
  - Non-hybrid `battery_soh` decreases as `age` increases (mileage held); Hybrid `battery_soh`
    decreases as `mileage` increases, and the drop is **non-linear** (mid-mileage marginal drop
    exceeds the low-mileage marginal drop).
  - `trans_adapt_offset` is **exactly `0.0`** for Manual and **strictly `< 0`** for every
    non-manual row; it grows more negative as mileage rises within the automatic path.
  - Feature engineering is **reproducible**: same input + same seed ⇒ identical engineered columns.

## Done criteria

- Three notebooks committed under `backend/ml/notebooks/` with cell outputs cleared, documenting
  the EDA → cleaning → modeling decisions.
- `python -m ml.train` writes `model.joblib` + `metrics.json`, with no import dependency on the
  notebooks.
- Predictor interface importable and returns the documented shapes.
- Gate-2 metrics reviewed and approved before Phase 03 depends on the real artifact.
- Caveat restated in `metrics.json` notes: prices are UK levels in RM via `FX_GBP_TO_RM`.
