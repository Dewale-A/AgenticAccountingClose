"""
Shared test fixtures for AgenticAccountingClose.

Provides:
- A temporary database initialized and seeded for each test session
- A FastAPI TestClient wired to the app
- A GovernanceEngine instance with default policy
"""

import os
import pytest
from fastapi.testclient import TestClient

# Override DATABASE_PATH before any src imports so the test database
# is used everywhere (database.py reads this env var on import).
@pytest.fixture(autouse=True, scope="session")
def _set_test_db(tmp_path_factory):
    """Point the database at a temporary file for the entire test session."""
    db_file = str(tmp_path_factory.mktemp("data") / "test_accounting.db")
    os.environ["DATABASE_PATH"] = db_file
    yield
    # Cleanup happens automatically when tmp_path is removed


@pytest.fixture(scope="session")
def db_path():
    """Return the current DATABASE_PATH (already set by _set_test_db)."""
    return os.environ["DATABASE_PATH"]


@pytest.fixture(scope="session")
def seeded_db(db_path):
    """Initialize and seed the test database once per session."""
    # Import after DATABASE_PATH is set
    from src.data.database import initialize_database, seed_database
    initialize_database()
    seed_database()
    return db_path


@pytest.fixture()
def governance_engine(seeded_db):
    """Return a GovernanceEngine with default policy."""
    from src.governance.engine import GovernanceEngine
    return GovernanceEngine()


@pytest.fixture()
def client(seeded_db):
    """Return a FastAPI TestClient connected to the app."""
    from src.api.routes import app
    return TestClient(app)
