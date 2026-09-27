import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# CRITICAL: this must run before ANY `app.*` module is imported (including
# by other test files), because app/core/database.py reads this env var
# exactly once at import time to decide which SQLite file to use. Every
# module that does `from app.core.database import SessionLocal` then shares
# that same test engine. conftest.py is always imported by pytest before
# test modules are collected, so this timing is guaranteed.
_tmp_dir = tempfile.mkdtemp()
os.environ["NOVATECH_DB_PATH"] = os.path.join(_tmp_dir, "test_novatech.db")

from app.core.database import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_test_database():
    init_db()
    yield
