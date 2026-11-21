import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# Must be set BEFORE the app is imported
_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = "sqlite:///" + _db_file
os.environ["MIN_METRIC_INTERVAL_SECONDS"] = "0"
os.environ["FRONTEND_DIST"] = os.path.join(tempfile.mkdtemp(), "no-dist")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def headers():
    import uuid
    return {"X-Client-Id": "client_" + uuid.uuid4().hex}
