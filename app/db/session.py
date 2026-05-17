import sqlite3
from app.core.config import DB_PATH

def get_db():
    """Returns a connection to the SQLite database with WAL mode and row factory enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist and performs necessary migrations."""
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
            source TEXT, -- 'pinterest', 'unsplash', etc.
            content_hash TEXT,
            status TEXT DEFAULT 'active',
            user_touched BOOLEAN DEFAULT FALSE,
            pinned_to_anchor TEXT,
            pin_note TEXT,
            last_used DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            legacy_path TEXT,
            provider TEXT DEFAULT 'unknown',
            api_type TEXT DEFAULT 'scraper',
            FOREIGN KEY (anchor_id) REFERENCES text_anchors(id)
        );

        CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY,
            anchor_id TEXT,
            video_id TEXT NOT NULL,
            video_title TEXT,
            video_url TEXT NOT NULL,
            thumbnail_path TEXT,
            thumbnail_url TEXT,
            timestamp_start REAL,
            timestamp_end REAL,
            transcript_snippet TEXT,
            keyword TEXT,
            source TEXT DEFAULT 'youtube',
            status TEXT DEFAULT 'active',
            clip_file_path TEXT,
            user_touched BOOLEAN DEFAULT FALSE,
            pinned_to_anchor TEXT,
            pin_note TEXT,
            last_used DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (anchor_id) REFERENCES text_anchors(id)
        );
        """)
    
    # Ensure columns exist (for legacy DBs)
    with get_db() as conn:
        cols_to_add = [
            ("content_hash", "TEXT"),
            ("source", "TEXT"),
            ("provider", "TEXT DEFAULT 'unknown'"),
            ("api_type", "TEXT DEFAULT 'scraper'")
        ]
        for col_name, col_def in cols_to_add:
            try:
                conn.execute(f"ALTER TABLE images ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass
