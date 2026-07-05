"""Predictor interface consumed by Phase 03.

predict(profile) -> {value_rm, low_rm, high_rm, confidence}
depreciation(profile, years) -> [{year, value_rm, retained_pct}, ...]

A prediction profile carries the harmonised core fields (model_class, year, age,
mileage, transmission, fuel_type, optional engine_size, optional source_market).
It is enriched with cars-spec vehicle specs the SAME way training rows are, then
the two simulated OBD-II features are re-derived noise-free so inference is stable.
`source_market` defaults to "uk" (predictions read as UK-price-level in RM unless a
market is supplied), consistent with the pooled model's honest FX caveat.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml import ingest
from ml.features import engineer_profile
from ml.train import FEATURES, INTERVAL_HIGH_PCT, INTERVAL_LOW_PCT

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[0] / "artifacts" / "model.joblib"
CONFIDENCE = (INTERVAL_HIGH_PCT - INTERVAL_LOW_PCT) / 100.0
DEFAULT_MARKET = "uk"


class Predictor:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH, specs: pd.DataFrame | None = None):
        self.pipe = joblib.load(model_path)
        self.prep = self.pipe.named_steps["prep"]
        self.rf = self.pipe.named_steps["model"]
        self.specs = ingest.clean_spec() if specs is None else specs

    def _row(self, profile: dict) -> pd.DataFrame:
        """Harmonise -> enrich with specs -> add noise-free OBD-II features."""
        model_class = ingest.canon_class(profile.get("model_class") or profile.get("model")) or "Unknown"
        engine_size = profile.get("engine_size", np.nan)
        one = pd.DataFrame([{
            "model_class": model_class,
            "year": profile.get("year"),
            "age": profile["age"],
            "mileage": profile["mileage"],
            "transmission": profile["transmission"],
            "fuel_type": profile["fuel_type"],
            "engine_size": engine_size if engine_size is not None else np.nan,
            "engine_hint": engine_size if engine_size is not None else np.nan,
            "source_market": profile.get("source_market", DEFAULT_MARKET),
        }])
        enriched = ingest.enrich(one, self.specs)
        eng = engineer_profile({
            "fuel_type": profile["fuel_type"],
            "transmission": profile["transmission"],
            "age": profile["age"],
            "mileage": profile["mileage"],
        })
        enriched["battery_soh"] = eng["battery_soh"]
        enriched["trans_adapt_offset"] = eng["trans_adapt_offset"]
        return enriched[FEATURES]

    def _per_tree(self, row: pd.DataFrame) -> np.ndarray:
        Xt = self.prep.transform(row)
        return np.array([est.predict(Xt)[0] for est in self.rf.estimators_])

    def predict(self, profile: dict) -> dict:
        trees = self._per_tree(self._row(profile))
        value = float(np.mean(trees))
        low = max(0.0, float(np.percentile(trees, INTERVAL_LOW_PCT)))
        high = float(np.percentile(trees, INTERVAL_HIGH_PCT))
        # For a skewed per-tree sample the mean can fall outside the [4,96] band;
        # clamp so the low_rm <= value_rm <= high_rm contract holds by construction.
        high = max(high, value)
        low = min(low, value)
        return {
            "value_rm": int(round(value)),
            "low_rm": int(round(low)),
            "high_rm": int(round(high)),
            "confidence": CONFIDENCE,
        }

    def depreciation(self, profile: dict, years: int = 5) -> list[dict]:
        base_year = int(profile["year"])
        base_age = int(profile["age"])
        raw_values = []
        for step in range(years + 1):
            future = {**profile, "age": base_age + step}  # mileage held fixed per spec
            raw_values.append(float(np.mean(self._per_tree(self._row(future)))))
        # enforce non-increasing (RF is not monotonic in age) and floor at 0
        monotonic = np.minimum.accumulate(np.maximum(raw_values, 0.0))
        # degenerate zero-valuation base -> today=1.0, so retained_pct[0] reads 0.0 (not 1.0)
        today = monotonic[0] if monotonic[0] > 0 else 1.0
        return [
            {
                "year": base_year + step,
                "value_rm": int(round(monotonic[step])),
                "retained_pct": round(float(monotonic[step] / today), 4),
            }
            for step in range(years + 1)
        ]


@lru_cache(maxsize=1)
def _default_predictor() -> Predictor:
    return Predictor()


def predict(profile: dict) -> dict:
    return _default_predictor().predict(profile)


def depreciation(profile: dict, years: int = 5) -> list[dict]:
    return _default_predictor().depreciation(profile, years=years)
