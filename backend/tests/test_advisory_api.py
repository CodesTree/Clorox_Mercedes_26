from fastapi.testclient import TestClient

from app.main import app
from app.routers import advisory
from app.schemas import DepreciationOut, DepreciationPoint, PredictOut


class RepairKeepPredictor:
    def predict(self, profile):
        return PredictOut(value_rm=738000, low_rm=712000, high_rm=765000, confidence=0.92)

    def depreciation(self, profile, years: int):
        assert years == 5
        return DepreciationOut(
            points=[
                DepreciationPoint(year=2026, value_rm=738000, retained_pct=1.0),
                DepreciationPoint(year=2031, value_rm=620000, retained_pct=0.8401),
            ]
        )


class SellPredictor:
    def predict(self, profile):
        return PredictOut(value_rm=738000, low_rm=712000, high_rm=765000, confidence=0.92)

    def depreciation(self, profile, years: int):
        assert years == 5
        return DepreciationOut(
            points=[
                DepreciationPoint(year=2026, value_rm=738000, retained_pct=1.0),
                DepreciationPoint(year=2031, value_rm=730000, retained_pct=0.9892),
            ]
        )


def test_advisory_interpret_recommends_repair_and_keep(monkeypatch):
    monkeypatch.setattr(advisory, "predictor_service", RepairKeepPredictor())

    with TestClient(app) as client:
        resp = client.get("/advisory/interpret", params={"profile_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation"] == "Repair and keep"
    assert body["horizon_years"] == 5
    assert body["current_value_rm"] == 738000
    assert body["horizon_value_rm"] == 620000
    assert body["depreciation_loss_rm"] == 118000
    assert body["total_repair_cost_rm"] == 18400
    assert body["llm_used"] is False
    assert len(body["repairs"]) == 3
    assert "Repair and keep is recommended" in body["summary"]


def test_advisory_interpret_recommends_sell(monkeypatch):
    monkeypatch.setattr(advisory, "predictor_service", SellPredictor())

    with TestClient(app) as client:
        resp = client.get("/advisory/interpret", params={"profile_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation"] == "Sell"
    assert body["depreciation_loss_rm"] == 8000
    assert body["total_repair_cost_rm"] == 18400
    assert "Selling is recommended" in body["summary"]
