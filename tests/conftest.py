import pytest
import sqlite3
import os
from fastapi.testclient import TestClient
from main import app
import db
from pathlib import Path
from unittest.mock import MagicMock

# Use a temporary database for testing
TEST_DB_PATH = Path("test_narrateimage.db")

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Remove test DB if it exists
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    
    # Initialize the test database schema
    # Temporarily monkeypatch DB_PATH in db module
    original_db_path = db.DB_PATH
    db.DB_PATH = TEST_DB_PATH
    db.init_db()
    
    yield
    
    # Cleanup after all tests
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    db.DB_PATH = original_db_path

@pytest.fixture
def test_db():
    """Provides a connection to the test database."""
    original_db_path = db.DB_PATH
    db.DB_PATH = TEST_DB_PATH
    conn = db.get_db()
    yield conn
    conn.close()
    db.DB_PATH = original_db_path

@pytest.fixture
def client(monkeypatch):
    """Provides a TestClient for the FastAPI app with DB overrides."""
    monkeypatch.setattr(db, "DB_PATH", TEST_DB_PATH)
    # We also need to monkeypatch 'get_db' in main.py if it's imported there
    def mock_get_db():
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    import main
    monkeypatch.setattr(main, "get_db", mock_get_db)
    
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_deepseek(monkeypatch):
    """Mocks the DeepSeek OpenAI client."""
    mock_client = MagicMock()
    import main
    monkeypatch.setattr(main, "client", mock_client)
    return mock_client

@pytest.fixture
def mock_scraper(monkeypatch):
    """Mocks Pinterest scraper functions."""
    import main
    mock_get = MagicMock(return_value=["http://example.com/img1.jpg"])
    mock_download = MagicMock()
    monkeypatch.setattr(main, "get_pinterest_images", mock_get)
    monkeypatch.setattr(main, "download_images", mock_download)
    return {"get": mock_get, "download": mock_download}
