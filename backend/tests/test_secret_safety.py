"""Spec invariant: the DB connection string never appears in responses or logs."""
import logging

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_database_url_never_leaks_into_responses_or_logs(caplog):
    secret = get_settings().database_url
    assert secret

    with caplog.at_level(logging.DEBUG):
        with TestClient(app) as client:
            health_text = client.get("/health").text
            openapi_text = client.get("/openapi.json").text
            error_text = client.get("/market/comps", params={"model": "X"}).text

    assert secret not in health_text
    assert secret not in openapi_text
    assert secret not in error_text
    assert secret not in caplog.text
