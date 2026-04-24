import pytest
import json
from pathlib import Path
import main

def test_list_scripts(client, tmp_path, monkeypatch):
    # Setup dummy script files
    scripts_dir = tmp_path / "video-scripts"
    scripts_dir.mkdir()
    (scripts_dir / "test1.md").write_text("content1")
    (scripts_dir / "test2.md").write_text("content2")
    
    # Patch SCRIPTS_DIR in main
    monkeypatch.setattr(main, "SCRIPTS_DIR", scripts_dir)
    
    response = client.get("/api/scripts")
    assert response.status_code == 200
    data = response.json()
    assert "test1.md" in data
    assert "test2.md" in data

def test_get_script(client, tmp_path, monkeypatch):
    scripts_dir = tmp_path / "video-scripts"
    scripts_dir.mkdir()
    (scripts_dir / "test1.md").write_text("script content")
    monkeypatch.setattr(main, "SCRIPTS_DIR", scripts_dir)
    
    response = client.get("/api/script/test1.md")
    assert response.status_code == 200
    assert response.json()["content"] == "script content"
    
    response = client.get("/api/script/missing.md")
    assert response.status_code == 404

def test_process_script(client, mock_deepseek, test_db):
    # Setup mock DeepSeek response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
        "segments": [
            {"id": 1, "text": "Segment 1", "keywords": ["kw1", "kw2"]},
            {"id": 2, "text": "Segment 2", "keywords": ["kw3"]}
        ]
    })))]
    mock_deepseek.chat.completions.create.return_value = mock_response
    
    # Mock prompt.txt read
    from unittest.mock import patch, mock_open
    with patch("builtins.open", mock_open(read_data="System prompt with {script_text}")):
        payload = {
            "filename": "test_script.md",
            "script_text": "Full script text"
        }
        
        response = client.post("/api/process-script", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["text"] == "Segment 1"
    
    # Check DB
    cursor = test_db.cursor()
    cursor.execute("SELECT id FROM scripts WHERE filename = 'test_script.md'")
    script = cursor.fetchone()
    assert script is not None
    
    cursor.execute("SELECT COUNT(*) FROM segments WHERE script_id = ?", (script[0],))
    assert cursor.fetchone()[0] == 2

from unittest.mock import MagicMock

def test_pin_image(client, test_db):
    # Insert a test image
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO images (id, file_path, status) VALUES (?, ?, ?)",
                   ("img123", "path/to/image.jpg", "active"))
    test_db.commit()
    
    payload = {
        "image_path": "path/to/image.jpg",
        "pin": True,
        "note": "Important image"
    }
    response = client.post("/api/pin-image", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "pinned"
    
    cursor.execute("SELECT status, pin_note FROM images WHERE id = 'img123'")
    row = cursor.fetchone()
    assert row["status"] == "pinned"
    assert row["pin_note"] == "Important image"

def test_delete_images(client, test_db):
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO images (id, file_path, status) VALUES (?, ?, ?)",
                   ("img456", "del/me.jpg", "active"))
    test_db.commit()
    
    payload = {"image_paths": ["del/me.jpg"]}
    response = client.post("/api/delete-images", json=payload)
    assert response.status_code == 200
    assert "del/me.jpg" in response.json()["deleted"]
    
    cursor.execute("SELECT status FROM images WHERE id = 'img456'")
    assert cursor.fetchone()["status"] == "deleted"

def test_download_keyword_images(client, mock_scraper, test_db, tmp_path, monkeypatch):
    # Setup: need a script and a segment in DB
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO scripts (id, filename) VALUES (?, ?)", ("script1", "test.md"))
    cursor.execute("INSERT INTO text_anchors (id, script_id, content, content_hash) VALUES (?, ?, ?, ?)",
                   ("anchor1", "script1", "Some text", "hash1"))
    cursor.execute("INSERT INTO segments (id, script_id, anchor_id, ai_index, keywords) VALUES (?, ?, ?, ?, ?)",
                   ("seg1", "script1", "anchor1", 1, '["key"]'))
    test_db.commit()
    
    # Mock DOWNLOAD_DIR
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    monkeypatch.setattr(main, "DOWNLOAD_DIR", download_dir)
    
    # Mock pinterest_scraper.download_image to actually "create" a file
    import pinterest_scraper
    def mock_download_func(url, path):
        Path(path).write_text("fake image data")
    monkeypatch.setattr(pinterest_scraper, "download_image", mock_download_func)
    
    payload = {
        "filename": "test.md",
        "segment_id": 1,
        "keyword": "key"
    }
    
    response = client.post("/api/download-keyword-images", json=payload)
    assert response.status_code == 200
    assert len(response.json()["images"]) == 1
    
    # Verify image record created
    cursor.execute("SELECT COUNT(*) FROM images WHERE anchor_id = 'anchor1'")
    assert cursor.fetchone()[0] == 1
