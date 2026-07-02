from fastapi.testclient import TestClient

from app.main import app

EXPECTED_PATHS = {
    "/health": {"get"},
    "/predict": {"post"},
    "/market/comps": {"get"},
    "/depreciation": {"get"},
    "/obd/snapshot": {"get"},
    "/obd/stream": {"get"},
    "/odx/faults": {"get"},
    "/vehicle/profile": {"get", "put"},
    "/booking": {"post"},
}


def test_openapi_exposes_the_full_contract():
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
    for path, methods in EXPECTED_PATHS.items():
        assert path in spec["paths"], f"missing path: {path}"
        have = set(spec["paths"][path].keys())
        assert methods <= have, f"{path}: expected {methods}, got {have}"


def test_stubs_return_503_not_500():
    with TestClient(app) as client:
        assert client.get("/market/comps", params={"model": "SL CLASS"}).status_code == 503
        assert client.get("/obd/snapshot", params={"profile_id": 1}).status_code == 503
        assert client.get("/odx/faults", params={"profile_id": 1}).status_code == 503
        assert client.get("/vehicle/profile", params={"id": 1}).status_code == 503
        assert client.get("/depreciation", params={"profile_id": 1}).status_code == 503
        body = {
            "model": "SL CLASS",
            "year": 2016,
            "mileage": 42000,
            "transmission": "Automatic",
            "fuel_type": "Petrol",
            "engine_size": 5.5,
        }
        assert client.post("/predict", json=body).status_code == 503


def test_validation_still_applies_to_stubs():
    with TestClient(app) as client:
        resp = client.post("/predict", json={"model": "SL CLASS"})
    assert resp.status_code == 422
