from pathlib import Path

from app.config import Settings


def test_defaults_load_without_env_file():
    s = Settings(_env_file=None)
    assert s.database_url.startswith("sqlite:///")
    assert s.fx_gbp_to_rm > 0
    assert "http://localhost:5173" in s.cors_origin_list


def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("FX_GBP_TO_RM", "6.25")
    assert Settings(_env_file=None).fx_gbp_to_rm == 6.25


def test_cors_origins_splits_on_comma():
    s = Settings(_env_file=None, cors_origins="http://a.test, http://b.test")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]


def test_default_env_file_is_repo_root_env_file():
    repo_root = Path(__file__).resolve().parents[2]
    assert Settings.model_config["env_file"] == repo_root / ".env"


def test_relative_google_calendar_credentials_path_resolves_from_backend_dir():
    backend_dir = Path(__file__).resolve().parents[1]

    settings = Settings(
        _env_file=None,
        google_calendar_credentials_json="./secrets/google_sa.json",
    )

    assert settings.google_calendar_credentials_json == str(
        backend_dir / "secrets" / "google_sa.json"
    )
