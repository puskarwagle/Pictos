import sqlite3
import json
from pathlib import Path
import hashlib
import uuid
from datetime import datetime

DB_PATH = Path("narrateimage.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS scripts (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS text_anchors (
            id TEXT PRIMARY KEY,
            script_id TEXT NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (script_id) REFERENCES scripts(id)
        );

        CREATE TABLE IF NOT EXISTS segments (
            id TEXT PRIMARY KEY,
            script_id TEXT NOT NULL,
            anchor_id TEXT NOT NULL,
            ai_index INTEGER,
            keywords TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anchor_id) REFERENCES text_anchors(id)
        );

        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            anchor_id TEXT,
            file_path TEXT NOT NULL,
            keyword TEXT,
            source_url TEXT,
            content_hash TEXT,
            status TEXT DEFAULT 'active',
            user_touched BOOLEAN DEFAULT FALSE,
            pinned_to_anchor TEXT,
            pin_note TEXT,
            last_used DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            legacy_path TEXT,
            FOREIGN KEY (anchor_id) REFERENCES text_anchors(id)
        );
        """)
    
    # Ensure content_hash column exists (for migrations)
    with get_db() as conn:
        try:
            conn.execute("ALTER TABLE images ADD COLUMN content_hash TEXT")
        except sqlite3.OperationalError:
            # Column already exists
            pass

def generate_id():
    return str(uuid.uuid4())

def hash_content(content: str) -> str:
    return hashlib.sha256(content.strip().encode('utf-8')).hexdigest()

def can_delete_file(file_path: str, conn: sqlite3.Connection) -> bool:
    """
    Checks if a physical file can be safely deleted.
    Returns True only if no active or pinned records reference this file path.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM images 
        WHERE (file_path = ? OR legacy_path = ?) 
        AND status != 'deleted'
    """, (file_path, file_path))
    count = cursor.fetchone()[0]
    return count == 0

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
