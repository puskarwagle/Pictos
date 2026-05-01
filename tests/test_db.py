import pytest
from app.db.repository import generate_id, hash_content, can_delete_file
from app.db import session
from app.core import config
import sqlite3
from pathlib import Path

def test_generate_id():
    id1 = generate_id()
    id2 = generate_id()
    assert isinstance(id1, str)
    assert len(id1) > 0
    assert id1 != id2

def test_hash_content():
    content = "Hello world"
    h1 = hash_content(content)
    h2 = hash_content(" Hello world ")
    assert h1 == h2
    assert h1 == hash_content("Hello world")

def test_can_delete_file(test_db):
    cursor = test_db.cursor()
    file_path = "test_image.jpg"
    
    # Initially should be deletable (not in DB)
    assert can_delete_file(file_path, test_db) is True
    
    # Add active record
    cursor.execute("INSERT INTO images (id, file_path, status) VALUES (?, ?, ?)", 
                   ("img1", file_path, "active"))
    test_db.commit()
    assert can_delete_file(file_path, test_db) is False
    
    # Change status to deleted
    cursor.execute("UPDATE images SET status = 'deleted' WHERE id = ?", ("img1",))
    test_db.commit()
    assert can_delete_file(file_path, test_db) is True
    
    # Add pinned record
    cursor.execute("UPDATE images SET status = 'pinned' WHERE id = ?", ("img1",))
    test_db.commit()
    assert can_delete_file(file_path, test_db) is False

def test_init_db(tmp_path, monkeypatch):
    test_db_file = tmp_path / "new_test.db"
    
    # Patch both config and session
    monkeypatch.setattr(config, "DB_PATH", test_db_file)
    monkeypatch.setattr(session, "DB_PATH", test_db_file)
    
    session.init_db()
    
    assert test_db_file.exists()
    conn = sqlite3.connect(test_db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "scripts" in tables
    assert "text_anchors" in tables
    assert "segments" in tables
    assert "images" in tables
    conn.close()
