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


class DepreciationOnlyPredictor:
    def predict(self, profile):
        raise AssertionError("advisory should use depreciation points for current and horizon values")

    def depreciation(self, profile, years: int):
        assert years == 5
        return DepreciationOut(
            points=[
                DepreciationPoint(year=2026, value_rm=500000, retained_pct=0.6775),
                DepreciationPoint(year=2031, value_rm=386890, retained_pct=0.5242),
            ]
        )


class SummaryClient:
    def __init__(self):
        self.facts = None

    def advisory_summary(self, facts):
        self.facts = facts
        return "Repair and keep is recommended because Gemini interpreted the calculated 5-year result."


class EmptySummaryClient:
    def advisory_summary(self, facts):
        return None


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


def test_advisory_uses_llm_summary_when_client_returns_text(monkeypatch):
    summary_client = SummaryClient()
    monkeypatch.setattr(advisory, "predictor_service", RepairKeepPredictor())
    monkeypatch.setattr(advisory, "summary_client", summary_client)

    with TestClient(app) as client:
        resp = client.get("/advisory/interpret", params={"profile_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_used"] is True
    assert body["summary"] == "Repair and keep is recommended because Gemini interpreted the calculated 5-year result."
    assert summary_client.facts["recommendation"] == "Repair and keep"
    assert summary_client.facts["depreciation_loss_rm"] == 118000


def test_advisory_falls_back_when_llm_summary_is_empty(monkeypatch):
    monkeypatch.setattr(advisory, "predictor_service", RepairKeepPredictor())
    monkeypatch.setattr(advisory, "summary_client", EmptySummaryClient())

    with TestClient(app) as client:
        resp = client.get("/advisory/interpret", params={"profile_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_used"] is False
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


def test_advisory_uses_depreciation_points_as_graph_source_of_truth(monkeypatch):
    monkeypatch.setattr(advisory, "predictor_service", DepreciationOnlyPredictor())

    with TestClient(app) as client:
        resp = client.get("/advisory/interpret", params={"profile_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_value_rm"] == 500000
    assert body["horizon_value_rm"] == 386890
    assert body["depreciation_loss_rm"] == 113110
