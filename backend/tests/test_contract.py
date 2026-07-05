from fastapi.testclient import TestClient

from app.main import app

EXPECTED_PATHS = {
    "/health": {"get"},
    "/predict": {"post"},
    "/advisory/interpret": {"get"},
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


def test_validation_still_applies_to_stubs():
    with TestClient(app) as client:
        resp = client.post("/predict", json={"model": "SL CLASS"})
    assert resp.status_code == 422
