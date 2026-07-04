"""RandomForest price predictor for the /predict/obd demo endpoint.

Loads the artifact trained by `backend/ml/notebooks/03_data_modelling/03_modeling.ipynb`
(`price_model.joblib` + `price_model_meta.json`). Prediction value and the
confidence/interval come from the spread of per-tree predictions, scaled by the
calibrated factor `k` stored in the metadata (≈80% empirical coverage).

Mirrors the lazy-load + graceful-unavailable pattern in `services/predictor.py`; heavy
deps (joblib/numpy/pandas) are imported only when a prediction is actually requested, so
importing the app never requires scikit-learn to be installed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas import PredictOut

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "ml" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "price_model.joblib"
META_PATH = ARTIFACT_DIR / "price_model_meta.json"

MODEL_UNAVAILABLE_DETAIL = (
    "price model unavailable: run "
    "backend/ml/notebooks/03_data_modelling/03_modeling.ipynb to train it"
)


class PriceModelUnavailable(RuntimeError):
    def __init__(self, detail: str = MODEL_UNAVAILABLE_DETAIL):
        super().__init__(detail)
        self.detail = detail


class PriceModelPredictor:
    def __init__(self, model_path: Path = MODEL_PATH, meta_path: Path = META_PATH):
        self.model_path = model_path
        self.meta_path = meta_path
        self._pipe: Any | None = None
        self._meta: dict[str, Any] | None = None

    def _load(self) -> None:
        if self._pipe is not None:
            return
        if not self.model_path.exists() or not self.meta_path.exists():
            raise PriceModelUnavailable()
        try:
            import joblib  # noqa: F401
        except ImportError as exc:
            raise PriceModelUnavailable(
                "install scikit-learn/joblib and train the model first"
            ) from exc
        import joblib

        self._pipe = joblib.load(self.model_path)
        self._meta = json.loads(self.meta_path.read_text(encoding="utf-8"))

    def predict(self, features: dict[str, Any]) -> PredictOut:
        """Predict price + confidence from a full feature payload (mock OBD-II + specs)."""
        self._load()
        import numpy as np
        import pandas as pd

        assert self._pipe is not None and self._meta is not None
        feature_order = self._meta["features"]
        row = pd.DataFrame([{name: features.get(name) for name in feature_order}])[feature_order]

        prep = self._pipe.named_steps["prep"]
        forest = self._pipe.named_steps["model"]
        transformed = prep.transform(row)

        # Per-tree predictions live in log space (target_transform == "log1p").
        per_tree = np.expm1(np.array([tree.predict(transformed)[0] for tree in forest.estimators_]))
        value = float(np.median(per_tree))
        spread = float(per_tree.std())

        k = float(self._meta["interval"]["k"])
        low = max(0.0, value - k * spread)
        high = value + k * spread
        confidence = float(np.clip(1.0 - (k * spread) / max(value, 1.0), 0.0, 1.0))

        return PredictOut(
            value_rm=int(round(value)),
            low_rm=int(round(low)),
            high_rm=int(round(high)),
            confidence=round(confidence, 3),
        )
