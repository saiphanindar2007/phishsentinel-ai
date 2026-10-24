import os
import sys
from pathlib import Path

# Make sure a fresh, throwaway SQLite DB is used for tests, and that the
# `app` package resolves regardless of the working directory pytest is
# invoked from (matches how training/ scripts do this too).
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_phishsentinel.db")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")  # tests fire many requests fast
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("ADMIN_API_KEY", "")
os.environ.setdefault("ENVIRONMENT", "test")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.database import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_test_db():
    init_db()
    yield


@pytest.fixture()
def client():
    return TestClient(app)
