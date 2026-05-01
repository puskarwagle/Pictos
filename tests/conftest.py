import pytest
import sqlite3
import os
from fastapi.testclient import TestClient
from main import app
from app.db import session, repository
from app.core import config
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Use a temporary database for testing
TEST_DB_PATH = Path("test_narrateimage.db")

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    
    # We must patch BOTH the config and any modules that already imported from it
    config.DB_PATH = TEST_DB_PATH
    session.DB_PATH = TEST_DB_PATH
    session.init_db()
    
    yield
    
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

@pytest.fixture
def test_db(monkeypatch):
    """Provides a connection to the test database."""
    monkeypatch.setattr(config, "DB_PATH", TEST_DB_PATH)
    monkeypatch.setattr(session, "DB_PATH", TEST_DB_PATH)
    conn = session.get_db()
    yield conn
    conn.close()

@pytest.fixture
def client(monkeypatch):
    """Provides a TestClient for the FastAPI app with DB overrides."""
    monkeypatch.setattr(config, "DB_PATH", TEST_DB_PATH)
    monkeypatch.setattr(session, "DB_PATH", TEST_DB_PATH)
    
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_ai_service(monkeypatch):
    """Mocks the AIService."""
    mock = MagicMock()
    # Mocking as an async function
    async def mock_process(script_text, source):
        return mock.process_script(script_text, source)
    
    monkeypatch.setattr("app.api.routes.ai_service.process_script", mock_process)
    return mock

@pytest.fixture
def mock_scrapers(monkeypatch):
    """Mocks scraper functions."""
    mock_pin = AsyncMock(return_value=["http://example.com/pin.jpg"])
    mock_uns = AsyncMock(return_value=["http://example.com/uns.jpg"])
    
    monkeypatch.setattr("app.api.routes.get_pinterest_images_async", mock_pin)
    monkeypatch.setattr("app.api.routes.get_unsplash_images_async", mock_uns)
    
    return {"pinterest": mock_pin, "unsplash": mock_uns}
