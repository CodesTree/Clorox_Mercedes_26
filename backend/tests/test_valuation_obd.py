"""Contract test for the /predict/obd demo endpoint (mock OBD-II + specs)."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.price_predictor import MODEL_PATH, META_PATH

MOCK_PATH = Path(__file__).resolve().parents[1] / "demo" / "mock_obd_car.json"


def _payload() -> dict:
    return json.loads(MOCK_PATH.read_text(encoding="utf-8"))


def test_predict_obd_returns_price_and_confidence():
    payload = _payload()
    with TestClient(app) as client:
        resp = client.post("/predict/obd", json=payload)

    if not (MODEL_PATH.exists() and META_PATH.exists()):
        # Artifact not trained in this environment -> endpoint degrades gracefully.
        assert resp.status_code == 503
        return

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["value_rm"] > 0
    assert body["low_rm"] <= body["value_rm"] <= body["high_rm"]
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["currency"] == "RM"


def test_predict_obd_rejects_incomplete_payload():
    payload = _payload()
    payload.pop("battery_soh")  # missing a required feature
    with TestClient(app) as client:
        resp = client.post("/predict/obd", json=payload)
    assert resp.status_code == 422
