"""Test bootstrap: force a throwaway SQLite file BEFORE any app import."""
import os
import tempfile
from pathlib import Path

_tmpdir = tempfile.mkdtemp(prefix="assetiq-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(_tmpdir) / 'test.db').as_posix()}"
