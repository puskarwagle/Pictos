from typing import List, Optional
import sqlite3
import json
from pathlib import Path
import hashlib
import uuid
from datetime import datetime

DB_PATH = Path("narrateimage.db")

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

def generate_id() -> str:
    """Generates a unique UUID string."""
    return str(uuid.uuid4())

def hash_content(content: str) -> str:
    """Returns a SHA256 hash of the normalized (trimmed) string content."""
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

# --- Repository Functions ---

def get_anchor_by_hash(cursor: sqlite3.Cursor, script_id: str, content_hash: str) -> Optional[str]:
    """Retrieves an anchor ID by its script ID and content hash for exact matching."""
    cursor.execute("SELECT id FROM text_anchors WHERE script_id = ? AND content_hash = ?", (script_id, content_hash))
    row = cursor.fetchone()
    return row[0] if row else None

def get_anchors_for_script(cursor: sqlite3.Cursor, script_id: str) -> List[sqlite3.Row]:
    """Retrieves all anchors associated with a specific script ID."""
    cursor.execute("SELECT id, content FROM text_anchors WHERE script_id = ?", (script_id,))
    return cursor.fetchall()

def update_anchor_content(cursor: sqlite3.Cursor, anchor_id: str, content: str, content_hash: str):
    """Updates the content and hash of an existing anchor."""
    cursor.execute("UPDATE text_anchors SET content = ?, content_hash = ? WHERE id = ?", 
                   (content, content_hash, anchor_id))

def create_anchor(cursor: sqlite3.Cursor, script_id: str, content: str, content_hash: str) -> str:
    """Creates a new text anchor and returns its ID."""
    new_id = generate_id()
    cursor.execute("INSERT INTO text_anchors (id, script_id, content, content_hash) VALUES (?, ?, ?, ?)",
                   (new_id, script_id, content, content_hash))
    return new_id

def get_anchor_id_by_ai_index(cursor: sqlite3.Cursor, filename: str, ai_index: int) -> Optional[str]:
    """Finds an anchor ID using the segment mapping for a specific script and AI index."""
    cursor.execute("""
        SELECT anchor_id FROM segments 
        WHERE script_id = (SELECT id FROM scripts WHERE filename = ?) 
        AND ai_index = ?
        ORDER BY created_at DESC LIMIT 1
    """, (filename, ai_index))
    row = cursor.fetchone()
    return row[0] if row else None

def get_anchor_id_by_filename_and_hash(cursor: sqlite3.Cursor, filename: str, content_hash: str) -> Optional[str]:
    """Finds an anchor ID for a specific script and content hash."""
    cursor.execute("""
        SELECT id FROM text_anchors 
        WHERE script_id = (SELECT id FROM scripts WHERE filename = ?) 
        AND content_hash = ?
    """, (filename, content_hash))
    row = cursor.fetchone()
    return row[0] if row else None

def update_images_last_used(cursor: sqlite3.Cursor, anchor_id: str):
    """Updates the last_used timestamp for all images associated with an anchor."""
    cursor.execute("UPDATE images SET last_used = CURRENT_TIMESTAMP WHERE anchor_id = ?", (anchor_id,))

def get_images_by_anchor(cursor: sqlite3.Cursor, anchor_id: str) -> List[sqlite3.Row]:
    """Retrieves all active or pinned images for a specific anchor."""
    cursor.execute("SELECT file_path, keyword, source FROM images WHERE anchor_id = ? AND status IN ('active', 'pinned')", (anchor_id,))
    return cursor.fetchall()

def get_script_id_by_filename(cursor: sqlite3.Cursor, filename: str) -> Optional[str]:
    """Retrieves the script ID for a given filename."""
    cursor.execute("SELECT id FROM scripts WHERE filename = ?", (filename,))
    row = cursor.fetchone()
    return row[0] if row else None

def create_script(cursor: sqlite3.Cursor, filename: str) -> str:
    """Creates a new script record and returns its ID."""
    script_id = generate_id()
    cursor.execute("INSERT INTO scripts (id, filename) VALUES (?, ?)", (script_id, filename))
    return script_id

def delete_segments_for_script(cursor: sqlite3.Cursor, script_id: str):
    """Deletes all segments associated with a script ID."""
    cursor.execute("DELETE FROM segments WHERE script_id = ?", (script_id,))

def create_segment(cursor: sqlite3.Cursor, script_id: str, anchor_id: str, ai_index: int, keywords: List[str]):
    """Creates a new segment mapping."""
    cursor.execute("""
        INSERT INTO segments (id, script_id, anchor_id, ai_index, keywords)
        VALUES (?, ?, ?, ?, ?)
    """, (generate_id(), script_id, anchor_id, ai_index, json.dumps(keywords)))

def orphan_unused_images(cursor: sqlite3.Cursor, script_id: str, current_anchor_ids: List[str]):
    """Marks images as orphaned if their anchors are no longer present in the script."""
    if not current_anchor_ids:
        # If no anchors provided, we might be clearing the script or it's an error.
        # Typically we want to avoid orphaning EVERYTHING unless intended.
        return
        
    cursor.execute("""
        SELECT DISTINCT anchor_id FROM segments 
        WHERE script_id = ? AND anchor_id NOT IN ({})
    """.format(','.join(['?']*len(current_anchor_ids))), (script_id, *current_anchor_ids))
    
    old_anchor_ids = [row[0] for row in cursor.fetchall()]
    if old_anchor_ids:
        cursor.execute("""
            UPDATE images 
            SET status = 'orphaned' 
            WHERE anchor_id IN ({}) 
            AND status = 'active' 
            AND user_touched = 0
        """.format(','.join(['?']*len(old_anchor_ids))), (*old_anchor_ids,))

def soft_delete_image(cursor: sqlite3.Cursor, file_path: str) -> int:
    """Soft deletes an image in the database by its file path or legacy path."""
    cursor.execute("UPDATE images SET status = 'deleted', user_touched = 1 WHERE file_path = ? OR legacy_path = ?", 
                   (file_path, file_path))
    return cursor.rowcount

def get_anchor_and_script_id(cursor: sqlite3.Cursor, filename: str, ai_index: int) -> Optional[sqlite3.Row]:
    """Retrieves both anchor ID and script ID for a specific segment."""
    cursor.execute("""
        SELECT s.anchor_id, sc.id as script_id
        FROM segments s
        JOIN scripts sc ON s.script_id = sc.id
        WHERE sc.filename = ? AND s.ai_index = ?
        ORDER BY s.created_at DESC LIMIT 1
    """, (filename, ai_index))
    return cursor.fetchone()

def get_existing_image_by_url(cursor: sqlite3.Cursor, url: str) -> Optional[sqlite3.Row]:
    """Checks if an image with the given URL already exists and is not deleted."""
    cursor.execute("""
        SELECT file_path, content_hash FROM images 
        WHERE source_url = ? AND status != 'deleted'
        LIMIT 1
    """, (url,))
    return cursor.fetchone()

def get_image_by_content_hash(cursor: sqlite3.Cursor, content_hash: str) -> Optional[str]:
    """Checks if an image with the given content hash already exists and is not deleted."""
    cursor.execute("""
        SELECT file_path FROM images 
        WHERE content_hash = ? AND status != 'deleted'
        LIMIT 1
    """, (content_hash,))
    row = cursor.fetchone()
    return row[0] if row else None

def insert_image(cursor: sqlite3.Cursor, anchor_id: str, file_path: str, keyword: str, url: str, source: str, content_hash: str, provider: str = 'unknown', api_type: str = 'scraper'):
    """Inserts a new image record into the database."""
    img_uuid = generate_id()
    cursor.execute("""
        INSERT INTO images (id, anchor_id, file_path, keyword, source_url, source, content_hash, provider, api_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (img_uuid, anchor_id, file_path, keyword, url, source, content_hash, provider, api_type))
    return img_uuid

def update_image_pinned_status(cursor: sqlite3.Cursor, file_path: str, is_pinned: bool, note: Optional[str] = None):
    """Updates the pinned status and note for an image."""
    status = 'pinned' if is_pinned else 'active'
    cursor.execute("""
        UPDATE images
        SET status = ?, pin_note = ?, user_touched = 1
        WHERE file_path = ? OR legacy_path = ?
    """, (status, note, file_path, file_path))


# --- Clip Repository Functions ---

def insert_clip(
    cursor: sqlite3.Cursor,
    anchor_id: str,
    video_id: str,
    video_title: str,
    video_url: str,
    thumbnail_path: Optional[str],
    thumbnail_url: Optional[str],
    timestamp_start: float,
    timestamp_end: float,
    transcript_snippet: str,
    keyword: str,
    source: str = 'youtube',
) -> str:
    """Inserts a new clip record into the database and returns its ID."""
    clip_id = generate_id()
    cursor.execute("""
        INSERT INTO clips (id, anchor_id, video_id, video_title, video_url,
                          thumbnail_path, thumbnail_url, timestamp_start, timestamp_end,
                          transcript_snippet, keyword, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (clip_id, anchor_id, video_id, video_title, video_url,
          thumbnail_path, thumbnail_url, timestamp_start, timestamp_end,
          transcript_snippet, keyword, source))
    return clip_id


def get_clips_by_anchor(cursor: sqlite3.Cursor, anchor_id: str) -> List[sqlite3.Row]:
    """Retrieves all active or pinned clips for a specific anchor."""
    cursor.execute("""
        SELECT id, video_id, video_title, video_url, thumbnail_path, thumbnail_url,
               timestamp_start, timestamp_end, transcript_snippet, keyword, source
        FROM clips
        WHERE anchor_id = ? AND status IN ('active', 'pinned')
    """, (anchor_id,))
    return cursor.fetchall()


def get_existing_clip(
    cursor: sqlite3.Cursor,
    video_id: str,
    timestamp_start: float,
    anchor_id: str
) -> Optional[sqlite3.Row]:
    """Checks if a clip with the same video_id and approximate timestamp already exists for this anchor."""
    cursor.execute("""
        SELECT id, thumbnail_path FROM clips
        WHERE video_id = ? AND anchor_id = ?
        AND ABS(timestamp_start - ?) < 5
        AND status != 'deleted'
        LIMIT 1
    """, (video_id, anchor_id, timestamp_start))
    return cursor.fetchone()


def update_clips_last_used(cursor: sqlite3.Cursor, anchor_id: str):
    """Updates the last_used timestamp for all clips associated with an anchor."""
    cursor.execute("UPDATE clips SET last_used = CURRENT_TIMESTAMP WHERE anchor_id = ?", (anchor_id,))


def soft_delete_clip(cursor: sqlite3.Cursor, clip_id: str) -> int:
    """Soft deletes a clip in the database by its ID."""
    cursor.execute("UPDATE clips SET status = 'deleted', user_touched = 1 WHERE id = ?", (clip_id,))
    return cursor.rowcount


def update_clip_pinned_status(cursor: sqlite3.Cursor, clip_id: str, is_pinned: bool, note: Optional[str] = None):
    """Updates the pinned status and note for a clip."""
    status = 'pinned' if is_pinned else 'active'
    cursor.execute("""
        UPDATE clips
        SET status = ?, pin_note = ?, user_touched = 1
        WHERE id = ?
    """, (status, note, clip_id))


def orphan_unused_clips(cursor: sqlite3.Cursor, script_id: str, current_anchor_ids: List[str]):
    """Marks clips as orphaned if their anchors are no longer present in the script."""
    if not current_anchor_ids:
        return

    cursor.execute("""
        SELECT DISTINCT anchor_id FROM segments
        WHERE script_id = ? AND anchor_id NOT IN ({})
    """.format(','.join(['?']*len(current_anchor_ids))), (script_id, *current_anchor_ids))

    old_anchor_ids = [row[0] for row in cursor.fetchall()]
    if old_anchor_ids:
        cursor.execute("""
            UPDATE clips
            SET status = 'orphaned'
            WHERE anchor_id IN ({})
            AND status = 'active'
            AND user_touched = 0
        """.format(','.join(['?']*len(old_anchor_ids))), (*old_anchor_ids,))

