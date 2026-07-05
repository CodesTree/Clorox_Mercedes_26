"""Test bootstrap: force a throwaway SQLite file BEFORE any app import."""
import os
import tempfile
from pathlib import Path

_tmpdir = tempfile.mkdtemp(prefix="assetiq-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_tmpdir) / 'test.db').as_posix()}"

# Keep tests hermetic: Settings now loads the repo-root .env, so blank out the
# integration secrets here (env vars override .env) to ensure the "unconfigured"
# defaults tests rely on. Tests that need configured behaviour construct explicit
# Settings(...) or monkeypatch the relevant functions.
for _secret in (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "GEMINI_API_KEY",
    "GOOGLE_CALENDAR_CREDENTIALS_JSON",
    "GOOGLE_CALENDAR_ID",
    "GOOGLE_CALENDAR_KEY",
):
    os.environ[_secret] = ""
