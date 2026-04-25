import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from pinterest_scraper import get_pinterest_images_async, download_images
from unsplash_scraper import get_unsplash_images_async
from pathlib import Path
import difflib
import hashlib
from db import init_db, get_db, hash_content, generate_id, can_delete_file

load_dotenv()

# Global semaphore to limit concurrent browser instances
BROWSER_SEMAPHORE = asyncio.Semaphore(2)

def get_image_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

app = FastAPI()

# Feature Flag
USE_DB_READ = os.getenv("USE_DB_READ", "False").lower() == "true"

@app.on_event("startup")
async def startup_event():
    init_db()

# Helper for Anchor Matching
def find_or_create_anchor(conn, script_id: str, content: str):
    cursor = conn.cursor()
    content_hash = hash_content(content)
    
    # 1. Exact Match
    cursor.execute("SELECT id FROM text_anchors WHERE script_id = ? AND content_hash = ?", (script_id, content_hash))
    row = cursor.fetchone()
    if row:
        return row[0]
        
    # 2. Fuzzy Match (difflib)
    cursor.execute("SELECT id, content FROM text_anchors WHERE script_id = ?", (script_id,))
    existing_anchors = cursor.fetchall()
    
    for anchor in existing_anchors:
        similarity = difflib.SequenceMatcher(None, content, anchor["content"]).ratio()
        if similarity >= 0.92:
            print(f"Fuzzy match found (similarity: {similarity:.2f}). Reusing anchor {anchor['id']}.")
            # Update the anchor with the new content and hash to ensure future exact matches
            cursor.execute("UPDATE text_anchors SET content = ?, content_hash = ? WHERE id = ?", 
                           (content, content_hash, anchor["id"]))
            return anchor["id"]
            
    # 3. No match, create new
    new_id = generate_id()
    cursor.execute("INSERT INTO text_anchors (id, script_id, content, content_hash) VALUES (?, ?, ?, ?)",
                   (new_id, script_id, content, content_hash))
    return new_id

# Configure DeepSeek client
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
)

# Ensure directories exist
DOWNLOAD_DIR = Path("downloaded_images")
SCRIPTS_DIR = Path("video-scripts")
RESPONSES_DIR = Path("ai_responses")
DOWNLOAD_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)
RESPONSES_DIR.mkdir(exist_ok=True)

class ScriptSegment(BaseModel):
    id: int
    text: str
    keywords: List[str]
    images: Optional[List[str]] = []

class ProcessRequest(BaseModel):
    filename: str
    script_text: str
    source: Optional[str] = "pinterest"

class DownloadRequest(BaseModel):
    filename: str
    segments: List[ScriptSegment]

def attach_images_to_segments(segments: List[dict], filename: str):
    if USE_DB_READ:
        conn = get_db()
        cursor = conn.cursor()
        for segment in segments:
            # Match by content hash (preferred) or fuzzy match if we want to be more resilient
            content = segment.get("text", "")
            content_hash = hash_content(content)
            ai_index = segment.get("id")
            
            # Find the anchor for this content in this script
            # 1. Try segments table (most accurate for processed scripts)
            cursor.execute("""
                SELECT anchor_id FROM segments 
                WHERE script_id = (SELECT id FROM scripts WHERE filename = ?) 
                AND ai_index = ?
                ORDER BY created_at DESC LIMIT 1
            """, (filename, ai_index))
            row = cursor.fetchone()
            
            anchor_id = None
            if row:
                anchor_id = row[0]
            else:
                # 2. Fallback to direct anchor lookup by hash
                cursor.execute("""
                    SELECT id FROM text_anchors 
                    WHERE script_id = (SELECT id FROM scripts WHERE filename = ?) 
                    AND content_hash = ?
                """, (filename, content_hash))
                row = cursor.fetchone()
                anchor_id = row[0] if row else None
            
            images = []
            downloaded_keywords = []
            
            if anchor_id:
                # Update last_used for all images attached to this anchor
                cursor.execute("UPDATE images SET last_used = CURRENT_TIMESTAMP WHERE anchor_id = ?", (anchor_id,))
                
                # Fetch active or pinned images - now including source
                cursor.execute("SELECT file_path, keyword, source FROM images WHERE anchor_id = ? AND status IN ('active', 'pinned')", (anchor_id,))
                rows = cursor.fetchall()
                images = [{"path": r["file_path"], "source": r["source"], "keyword": r["keyword"]} for r in rows]
                downloaded_keywords = list(set([r["keyword"] for r in rows if r["keyword"]]))
            
            segment["images"] = images
            segment["downloaded_keywords"] = downloaded_keywords
        conn.commit()
        conn.close()
    else:
        # Legacy filesystem scanning
        script_stem = Path(filename).stem
        for segment in segments:
            images = []
            downloaded_keywords = []
            if "keywords" in segment:
                # Strictly use the structured hierarchy: downloaded_images/script_name/segment_no/*/
                segment_base_dir = DOWNLOAD_DIR / script_stem / str(segment["id"])
                if segment_base_dir.exists():
                    for kw_dir in segment_base_dir.iterdir():
                        if kw_dir.is_dir():
                            kw_images = [f.as_posix() for f in kw_dir.glob("*.jpg")]
                            if kw_images:
                                # Legacy scanning doesn't easily know the source, defaulting to unknown
                                images.extend([{"path": img, "source": "unknown"} for img in kw_images])
                                downloaded_keywords.append(kw_dir.name.replace("_", " "))
            
            segment["images"] = images
            segment["downloaded_keywords"] = downloaded_keywords
    return segments

@app.get("/api/scripts")
async def list_scripts():
    scripts = [f.name for f in SCRIPTS_DIR.glob("*.md")]
    return scripts

@app.get("/api/script/{filename}")
async def get_script(filename: str):
    script_path = SCRIPTS_DIR / filename
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    with open(script_path, "r") as f:
        return {"content": f.read()}

@app.get("/api/script/{filename}/response")
async def get_script_response(filename: str):
    # Use stem to avoid "part1.md.json"
    stem = Path(filename).stem
    response_file = RESPONSES_DIR / f"{stem}.json"
    if not response_file.exists():
        raise HTTPException(status_code=404, detail=f"No cached response found at {response_file}")
    with open(response_file, "r") as f:
        data = json.load(f)
        segments = data.get("segments", data) if isinstance(data, dict) else data
        return attach_images_to_segments(segments, filename)

import string

async def call_ai(prompt: str):
    """Helper to call DeepSeek AI asynchronously."""
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts visual keywords from scripts. Output strictly valid JSON."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

@app.post("/api/process-script")
async def process_script(request: ProcessRequest):
    try:
        if request.source == "both":
            with open("prompt_pinterest.txt", "r") as f:
                p_pin = f.read()
            with open("prompt_unsplash.txt", "r") as f:
                p_uns = f.read()
            
            t_pin = string.Template(p_pin.replace("{script_text}", "$script_text"))
            t_uns = string.Template(p_uns.replace("{script_text}", "$script_text"))
            
            prompt_pin = t_pin.substitute(script_text=request.script_text)
            prompt_uns = t_uns.substitute(script_text=request.script_text)
            
            # Parallel calls
            res_pin, res_uns = await asyncio.gather(call_ai(prompt_pin), call_ai(prompt_uns))
            
            segs_pin = res_pin.get("segments", res_pin)
            segs_uns = res_uns.get("segments", res_uns)
            
            # Merge results
            merged_segments = []
            for i in range(max(len(segs_pin), len(segs_uns))):
                s_pin = segs_pin[i] if i < len(segs_pin) else {"text": "", "keywords": [], "id": i}
                s_uns = segs_uns[i] if i < len(segs_uns) else {"text": "", "keywords": [], "id": i}
                
                merged_segments.append({
                    "id": s_pin.get("id", i),
                    "text": s_pin.get("text") or s_uns.get("text"),
                    "keywords": s_pin.get("keywords", []) + ["|"] + s_uns.get("keywords", [])
                })
            result = {"segments": merged_segments}
        else:
            prompt_file = "prompt_pinterest.txt" if request.source == "pinterest" else "prompt_unsplash.txt"
            with open(prompt_file, "r") as f:
                prompt_template = f.read()
            
            t = string.Template(prompt_template.replace("{script_text}", "$script_text"))
            prompt = t.substitute(script_text=request.script_text)
            result = await call_ai(prompt)

        # Save the AI response to a file (legacy fallback)
        stem = Path(request.filename).stem
        response_file = RESPONSES_DIR / f"{stem}.json"
        print(f"Saving response to {response_file}")
        with open(response_file, "w") as f:
            json.dump(result, f, indent=4)

        segments = result.get("segments", result) if isinstance(result, dict) else result
        
        # --- DB Update ---
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Get or create script
        cursor.execute("SELECT id FROM scripts WHERE filename = ?", (request.filename,))
        row = cursor.fetchone()
        if row:
            script_id = row[0]
        else:
            script_id = generate_id()
            cursor.execute("INSERT INTO scripts (id, filename) VALUES (?, ?)", (script_id, request.filename))
        
        # Clear old segments for this script to avoid duplicates
        cursor.execute("DELETE FROM segments WHERE script_id = ?", (script_id,))

        # 2. Process segments into DB
        new_anchor_ids = set()
        for segment in segments:
            anchor_id = find_or_create_anchor(conn, script_id, segment.get("text", ""))
            new_anchor_ids.add(anchor_id)
            
            # Create segment view
            cursor.execute("""
                INSERT INTO segments (id, script_id, anchor_id, ai_index, keywords)
                VALUES (?, ?, ?, ?, ?)
            """, (generate_id(), script_id, anchor_id, segment.get("id"), json.dumps(segment.get("keywords", []))))

        
        # 3. Orphan images linked to anchors no longer in this script
        # Find all anchors previously associated with this script that are NOT in the new set
        cursor.execute("""
            SELECT DISTINCT anchor_id FROM segments 
            WHERE script_id = ? AND anchor_id NOT IN ({})
        """.format(','.join(['?']*len(new_anchor_ids))), (script_id, *new_anchor_ids))
        
        old_anchor_ids = [row[0] for row in cursor.fetchall()]
        if old_anchor_ids:
            cursor.execute("""
                UPDATE images 
                SET status = 'orphaned' 
                WHERE anchor_id IN ({}) 
                AND status = 'active' 
                AND user_touched = 0
            """.format(','.join(['?']*len(old_anchor_ids))), (*old_anchor_ids,))
        
        conn.commit()
        conn.close()
        # -----------------

        return attach_images_to_segments(segments, request.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class KeywordDownloadRequest(BaseModel):
    filename: str
    segment_id: int
    keyword: str
    source: Optional[str] = "pinterest"

class DeleteImagesRequest(BaseModel):
    image_paths: List[str]

@app.post("/api/delete-images")
async def delete_images(request: DeleteImagesRequest):
    conn = get_db()
    cursor = conn.cursor()
    deleted_paths = []
    
    for path_str in request.image_paths:
        # Soft delete in DB
        cursor.execute("UPDATE images SET status = 'deleted', user_touched = 1 WHERE file_path = ? OR legacy_path = ?", 
                       (path_str, path_str))
        if cursor.rowcount > 0:
            deleted_paths.append(path_str)
            # We don't unlink from disk yet (soft delete)
            # But the existing UI expects them to "disappear", so we return them as deleted.
            
    conn.commit()
    conn.close()
    return {"deleted": deleted_paths}

@app.post("/api/download-keyword-images")
async def download_keyword_images(request: KeywordDownloadRequest):
    # 1. Get anchor_id from DB
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.anchor_id, sc.id as script_id
        FROM segments s
        JOIN scripts sc ON s.script_id = sc.id
        WHERE sc.filename = ? AND s.ai_index = ?
        ORDER BY s.created_at DESC LIMIT 1
    """, (request.filename, request.segment_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Segment not found in database. Process script first.")
    
    anchor_id, script_id = row[0], row[1]
    
    # 2. Scrape
    try:
        source_urls = [] # list of (url, source_name)
        
        async with BROWSER_SEMAPHORE:
            if request.source == "pinterest":
                urls = await get_pinterest_images_async(request.keyword, 3, True)
                source_urls = [(u, "pinterest") for u in urls]
            elif request.source == "unsplash":
                urls = await get_unsplash_images_async(request.keyword, 3, True)
                source_urls = [(u, "unsplash") for u in urls]
            elif request.source == "both":
                # Serializing to avoid memory corruption from parallel browser initialization
                urls_pin = await get_pinterest_images_async(request.keyword, 2, True)
                urls_uns = await get_unsplash_images_async(request.keyword, 2, True)
                source_urls = [(u, "pinterest") for u in urls_pin] + [(u, "unsplash") for u in urls_uns]
        
        new_images = []
        if source_urls:
            from pinterest_scraper import download_image
            # Stable directory for script: downloaded_images/{script_id}/
            script_dir = DOWNLOAD_DIR / script_id
            script_dir.mkdir(parents=True, exist_ok=True)
            
            loop = asyncio.get_running_loop()
            for url, img_source in source_urls:
                # Step 1: Pre-download URL Dedup
                cursor.execute("""
                    SELECT file_path, content_hash FROM images 
                    WHERE source_url = ? AND status != 'deleted'
                    LIMIT 1
                """, (url,))
                existing = cursor.fetchone()
                
                if existing:
                    existing_path, existing_hash = existing[0], existing[1]
                    img_uuid = generate_id()
                    cursor.execute("""
                        INSERT INTO images (id, anchor_id, file_path, keyword, source_url, source, content_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (img_uuid, anchor_id, existing_path, request.keyword, url, img_source, existing_hash))
                    new_images.append({"path": existing_path, "source": img_source, "keyword": request.keyword})
                    continue

                # Step 2: Download and Content Hash Dedup
                img_uuid = generate_id()
                file_path = script_dir / f"{img_uuid}.jpg"
                path_str = file_path.as_posix()
                
                await loop.run_in_executor(None, download_image, url, file_path)
                
                if file_path.exists():
                    img_hash = get_image_hash(file_path)
                    
                    # Check for content hash match
                    cursor.execute("""
                        SELECT file_path FROM images 
                        WHERE content_hash = ? AND status != 'deleted'
                        LIMIT 1
                    """, (img_hash,))
                    hash_match = cursor.fetchone()
                    
                    if hash_match:
                        # Found duplicate by content!
                        match_path = hash_match[0]
                        # Delete the just-downloaded file (we don't need the helper here yet because we JUST created it)
                        os.remove(file_path)
                        
                        cursor.execute("""
                            INSERT INTO images (id, anchor_id, file_path, keyword, source_url, source, content_hash)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (img_uuid, anchor_id, match_path, request.keyword, url, img_source, img_hash))
                        new_images.append({"path": match_path, "source": img_source, "keyword": request.keyword})
                    else:
                        # Record in DB normally
                        cursor.execute("""
                            INSERT INTO images (id, anchor_id, file_path, keyword, source_url, source, content_hash)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (img_uuid, anchor_id, path_str, request.keyword, url, img_source, img_hash))
                        new_images.append({"path": path_str, "source": img_source, "keyword": request.keyword})
                else:
                    print(f"Failed to download image from {url}")
            
            conn.commit()
            conn.close()
            return {"images": new_images}
            
        conn.close()
        return {"images": []}
    except Exception as e:
        print(f"Error scraping for keyword {request.keyword}: {e}")
        if conn: conn.close()
        raise HTTPException(status_code=500, detail=str(e))

class PinImageRequest(BaseModel):
    image_path: str
    pin: bool
    note: Optional[str] = None

@app.post("/api/pin-image")
async def pin_image(request: PinImageRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    status = 'pinned' if request.pin else 'active'
    cursor.execute("""
        UPDATE images 
        SET status = ?, pin_note = ?, user_touched = 1 
        WHERE file_path = ? OR legacy_path = ?
    """, (status, request.note, request.image_path, request.image_path))
    
    conn.commit()
    conn.close()
    return {"status": status}

@app.post("/api/download-images")
async def download_script_images(request: DownloadRequest):
    results = []
    script_stem = Path(request.filename).stem
    
    for segment in request.segments:
        segment_id = segment.id
        # Use the first keyword for searching
        if not segment.keywords:
            results.append(segment)
            continue
            
        primary_keyword = segment.keywords[0]
        # New hierarchy: script_name/segment_no/keyword_title/
        subfolder_name = f"{script_stem}/{segment_id}/{primary_keyword.replace(' ', '_')}"
        segment_dir = DOWNLOAD_DIR / subfolder_name

        # Check if images already exist
        if segment_dir.exists() and any(segment_dir.glob("*.jpg")):
            print(f"Images already exist for {primary_keyword} in {subfolder_name}, skipping download.")
            segment.images = [{"path": f.as_posix(), "source": "unknown"} for f in segment_dir.glob("*.jpg")]
            results.append(segment)
            continue
        
        # Run scraping
        try:
            async with BROWSER_SEMAPHORE:
                img_urls = await get_pinterest_images_async(
                    primary_keyword, 
                    3, # number of images per segment
                    True # headless
                )
            
            if img_urls:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    download_images,
                    img_urls,
                    subfolder_name
                )
                
                # Get the local paths of downloaded images
                image_files = [{"path": f.as_posix(), "source": "pinterest"} for f in segment_dir.glob("*.jpg")]
                segment.images = image_files
        except Exception as e:
            print(f"Error scraping for segment {segment_id}: {e}")
            
        results.append(segment)
        
    return results


# Serve static files
app.mount("/static", StaticFiles(directory=os.path.abspath("static")), name="static")
app.mount("/downloaded_images", StaticFiles(directory=os.path.abspath("downloaded_images")), name="images")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("templates/index.html", "r") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
