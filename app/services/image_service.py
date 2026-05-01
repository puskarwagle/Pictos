import os
import asyncio
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import DOWNLOAD_DIR, USE_DB_READ, BASE_DIR
from app.db.session import get_db
from app.db.repository import (
    hash_content, get_anchor_id_by_ai_index, get_anchor_id_by_filename_and_hash,
    update_images_last_used, get_images_by_anchor, generate_id, get_existing_image_by_url,
    insert_image, get_image_by_content_hash
)

# Global semaphore to limit concurrent browser instances
BROWSER_SEMAPHORE = asyncio.Semaphore(2)

def get_image_hash(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def attach_images_to_segments(segments: List[dict], filename: str) -> List[dict]:
    """
    Attaches existing image metadata from the database (or legacy filesystem) to script segments.
    """
    if USE_DB_READ:
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
            
            images = []
            downloaded_keywords = []
            
            if anchor_id:
                update_images_last_used(cursor, anchor_id)
                rows = get_images_by_anchor(cursor, anchor_id)
                images = []
                for r in rows:
                    try:
                        p = Path(r["file_path"])
                        # If it's already relative, relative_to might fail if it doesn't start with BASE_DIR
                        # But we assume absolute paths are stored in DB.
                        if p.is_absolute():
                            rel_path = p.relative_to(BASE_DIR).as_posix()
                        else:
                            rel_path = p.as_posix()
                    except ValueError:
                        rel_path = r["file_path"]
                    images.append({"path": rel_path, "source": r["source"], "keyword": r["keyword"]})
                downloaded_keywords = list(set([r["keyword"] for r in rows if r["keyword"]]))
            
            segment["images"] = images
            segment["downloaded_keywords"] = downloaded_keywords
        conn.commit()
        conn.close()
    else:
        # Legacy filesystem scanning
        script_stem = Path(filename).stem
        for i, segment in enumerate(segments):
            images = []
            downloaded_keywords = []
            if "keywords" in segment:
                seg_id = segment.get("id", i)
                segment_base_dir = DOWNLOAD_DIR / script_stem / str(seg_id)
                if segment_base_dir.exists():
                    for kw_dir in segment_base_dir.iterdir():
                        if kw_dir.is_dir():
                            kw_images = [f.as_posix() for f in kw_dir.glob("*.jpg")]
                            if kw_images:
                                for img in kw_images:
                                    try:
                                        p = Path(img)
                                        if p.is_absolute():
                                            rel_p = p.relative_to(BASE_DIR).as_posix()
                                        else:
                                            rel_p = p.as_posix()
                                    except ValueError:
                                        rel_p = img
                                    images.append({"path": rel_p, "source": "unknown"})
                                downloaded_keywords.append(kw_dir.name.replace("_", " "))
            
            segment["images"] = images
            segment["downloaded_keywords"] = downloaded_keywords
    return segments

async def download_image_from_url(url: str, file_path: Path):
    """Downloads an image from a URL using httpx."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        file_path.write_bytes(resp.content)

async def process_and_store_image(
    url: str, 
    anchor_id: str, 
    script_id: str, 
    keyword: str, 
    source: str, 
    provider: str = 'unknown', 
    api_type: str = 'scraper'
) -> Optional[Dict[str, Any]]:
    """Handles deduping, downloading, and DB insertion for a single image."""
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. URL Dedup
    existing = get_existing_image_by_url(cursor, url)
    if existing:
        existing_path, existing_hash = existing["file_path"], existing["content_hash"]
        insert_image(cursor, anchor_id, existing_path, keyword, url, source, existing_hash, provider, api_type)
        conn.commit()
        conn.close()
        return {"path": existing_path, "source": source, "keyword": keyword}
    
    conn.close()

    # 2. Download
    script_dir = DOWNLOAD_DIR / script_id
    script_dir.mkdir(parents=True, exist_ok=True)
    
    img_uuid = generate_id()
    # Basic extension detection
    ext = ".jpg"
    if ".png" in url: ext = ".png"
    elif ".svg" in url: ext = ".svg"
    
    file_path = script_dir / f"{img_uuid}{ext}"
    path_str = file_path.as_posix()
    
    try:
        await download_image_from_url(url, file_path)
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None

    if file_path.exists():
        conn = get_db()
        cursor = conn.cursor()
        img_hash = get_image_hash(file_path)
        
        # 3. Content Hash Dedup
        match_path = get_image_by_content_hash(cursor, img_hash)
        if match_path:
            os.remove(file_path)
            insert_image(cursor, anchor_id, match_path, keyword, url, source, img_hash, provider, api_type)
            final_path = match_path
        else:
            insert_image(cursor, anchor_id, path_str, keyword, url, source, img_hash, provider, api_type)
            final_path = path_str
            
        conn.commit()
        conn.close()
        try:
            p = Path(final_path)
            if p.is_absolute():
                rel_final = p.relative_to(BASE_DIR).as_posix()
            else:
                rel_final = p.as_posix()
        except ValueError:
            rel_final = final_path
        return {"path": rel_final, "source": source, "keyword": keyword, "size": file_path.stat().st_size if not match_path else 0}
    
    return None
