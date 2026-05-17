"""
Clip Service — handles storing, retrieving, and managing YouTube clip metadata.
Replaces the old image_service.py for the video clip workflow.
"""

import hashlib
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from app.core.config import CLIPS_DIR, BASE_DIR, USE_DB_READ
from app.db.session import get_db
from app.db.repository import (
    generate_id, get_clips_by_anchor, insert_clip,
    get_existing_clip, get_anchor_id_by_ai_index,
    get_anchor_id_by_filename_and_hash, hash_content,
    update_clips_last_used
)


def attach_clips_to_segments(segments: List[dict], filename: str) -> List[dict]:
    """
    Attaches existing clip metadata from the database to script segments.
    Replaces the old attach_images_to_segments.
    """
    conn = get_db()
    cursor = conn.cursor()
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue

        content = segment.get("text", "")
        content_hash = hash_content(content)
        ai_index = segment.get("id")

        anchor_id = get_anchor_id_by_ai_index(cursor, filename, ai_index)
        if not anchor_id:
            anchor_id = get_anchor_id_by_filename_and_hash(cursor, filename, content_hash)

        clips = []
        downloaded_keywords = []

        if anchor_id:
            update_clips_last_used(cursor, anchor_id)
            rows = get_clips_by_anchor(cursor, anchor_id)
            for r in rows:
                thumb_path = r["thumbnail_path"] or ""
                if thumb_path:
                    try:
                        p = Path(thumb_path)
                        if p.is_absolute():
                            thumb_path = p.relative_to(BASE_DIR).as_posix()
                        else:
                            thumb_path = p.as_posix()
                    except ValueError:
                        pass

                clips.append({
                    "id": r["id"],
                    "video_id": r["video_id"],
                    "title": r["video_title"],
                    "url": r["video_url"],
                    "thumbnail": r["thumbnail_url"],
                    "thumbnail_path": thumb_path,
                    "timestamp_start": r["timestamp_start"],
                    "timestamp_end": r["timestamp_end"],
                    "transcript_snippet": r["transcript_snippet"],
                    "keyword": r["keyword"],
                    "source": r["source"],
                })
            downloaded_keywords = list(set([r["keyword"] for r in rows if r["keyword"]]))

        segment["clips"] = clips
        segment["downloaded_keywords"] = downloaded_keywords
        # Keep images key empty for backward compat during transition
        if "images" not in segment:
            segment["images"] = []

    conn.commit()
    conn.close()
    return segments


async def download_thumbnail(thumbnail_url: str, file_path: Path) -> bool:
    """Downloads a YouTube thumbnail to local storage."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(thumbnail_url)
            resp.raise_for_status()
            file_path.write_bytes(resp.content)
            return True
    except Exception as e:
        print(f"Failed to download thumbnail {thumbnail_url}: {e}")
        return False


async def process_and_store_clip(
    clip_data: Dict[str, Any],
    anchor_id: str,
    script_id: str,
    keyword: str,
) -> Optional[Dict[str, Any]]:
    """
    Handles deduplication and DB insertion for a single YouTube clip.
    Downloads the thumbnail locally.
    """
    conn = get_db()
    cursor = conn.cursor()

    video_id = clip_data["video_id"]
    timestamp_start = clip_data.get("timestamp_start", 0)

    # Dedup: check if this exact video+timestamp combo already exists for this anchor
    existing = get_existing_clip(cursor, video_id, timestamp_start, anchor_id)
    if existing:
        conn.close()
        return {
            "id": existing["id"],
            "video_id": video_id,
            "title": clip_data.get("title", ""),
            "url": clip_data["url"],
            "thumbnail": clip_data.get("thumbnail", ""),
            "thumbnail_path": existing["thumbnail_path"] or "",
            "timestamp_start": timestamp_start,
            "timestamp_end": clip_data.get("timestamp_end", timestamp_start + 10),
            "transcript_snippet": clip_data.get("transcript_snippet", ""),
            "keyword": keyword,
            "source": "youtube",
            "is_duplicate": True,
        }

    conn.close()

    # Download thumbnail
    thumb_dir = CLIPS_DIR / script_id
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_filename = f"{video_id}_{int(timestamp_start)}.jpg"
    thumb_path = thumb_dir / thumb_filename
    thumb_path_str = thumb_path.as_posix()

    thumbnail_url = clip_data.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
    await download_thumbnail(thumbnail_url, thumb_path)

    # Insert into DB
    conn = get_db()
    cursor = conn.cursor()
    clip_id = insert_clip(
        cursor,
        anchor_id=anchor_id,
        video_id=video_id,
        video_title=clip_data.get("title", ""),
        video_url=clip_data["url"],
        thumbnail_path=thumb_path_str if thumb_path.exists() else None,
        thumbnail_url=thumbnail_url,
        timestamp_start=timestamp_start,
        timestamp_end=clip_data.get("timestamp_end", timestamp_start + 10),
        transcript_snippet=clip_data.get("transcript_snippet", ""),
        keyword=keyword,
        source="youtube",
    )
    conn.commit()
    conn.close()

    # Build relative path for frontend
    rel_thumb = ""
    if thumb_path.exists():
        try:
            rel_thumb = thumb_path.relative_to(BASE_DIR).as_posix()
        except ValueError:
            rel_thumb = thumb_path_str

    return {
        "id": clip_id,
        "video_id": video_id,
        "title": clip_data.get("title", ""),
        "url": clip_data["url"],
        "thumbnail": thumbnail_url,
        "thumbnail_path": rel_thumb,
        "timestamp_start": timestamp_start,
        "timestamp_end": clip_data.get("timestamp_end", timestamp_start + 10),
        "transcript_snippet": clip_data.get("transcript_snippet", ""),
        "keyword": keyword,
        "source": "youtube",
        "is_duplicate": False,
    }
