import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
import time
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from openai import OpenAI
from pinterest_scraper import get_pinterest_images_async, download_images
from unsplash_scraper import get_unsplash_images_async
from pathlib import Path
import difflib
import hashlib
from db import (
    init_db, get_db, hash_content, generate_id, can_delete_file,
    get_anchor_by_hash, get_anchors_for_script, update_anchor_content, create_anchor,
    get_anchor_id_by_ai_index, get_anchor_id_by_filename_and_hash, update_images_last_used,
    get_images_by_anchor, get_script_id_by_filename, create_script, delete_segments_for_script,
    create_segment, orphan_unused_images, soft_delete_image, get_anchor_and_script_id,
    get_existing_image_by_url, get_image_by_content_hash, insert_image, update_image_pinned_status
)
from providers import PROVIDERS, API_PROVIDERS
import httpx

from models import (
    ScriptSegment, 
    ProcessRequest, 
    DownloadRequest, 
    KeywordDownloadRequest, 
    DeleteImagesRequest, 
    ApiFetchRequest, 
    PinImageRequest
)

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
    """
    Finds an existing text anchor for a given script or creates a new one.
    Implements a two-stage matching process:
    1. Exact Match: Checks if the content hash already exists for this script.
    2. Fuzzy Match: Uses difflib to find existing anchors with >92% similarity,
       allowing for minor edits in the text editor without losing image associations.
    """
    cursor = conn.cursor()
    content_hash = hash_content(content)
    
    # 1. Exact Match
    anchor_id = get_anchor_by_hash(cursor, script_id, content_hash)
    if anchor_id:
        return anchor_id
        
    # 2. Fuzzy Match (difflib)
    existing_anchors = get_anchors_for_script(cursor, script_id)
    
    for anchor in existing_anchors:
        similarity = difflib.SequenceMatcher(None, content, anchor["content"]).ratio()
        if similarity >= 0.92:
            print(f"Fuzzy match found (similarity: {similarity:.2f}). Reusing anchor {anchor['id']}.")
            # Update the anchor with the new content and hash to ensure future exact matches
            update_anchor_content(cursor, anchor["id"], content, content_hash)
            return anchor["id"]
            
    # 3. No match, create new
    return create_anchor(cursor, script_id, content, content_hash)

# Configure DeepSeek client
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=300.0  # Increased timeout for long scripts
)

# Ensure directories exist
DOWNLOAD_DIR = Path("downloaded_images")
SCRIPTS_DIR = Path("video-scripts")
RESPONSES_DIR = Path("ai_responses")
DOWNLOAD_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)
RESPONSES_DIR.mkdir(exist_ok=True)

def attach_images_to_segments(segments: List[dict], filename: str):
    """
    Attaches existing image metadata from the database (or legacy filesystem) to script segments.
    This allows the UI to display previously downloaded or pinned images immediately.
    """
    if USE_DB_READ:
        conn = get_db()
        cursor = conn.cursor()
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                print(f"Warning: segment is not a dict: {segment}")
                continue
            
            content = segment.get("text", "")
            content_hash = hash_content(content)
            ai_index = segment.get("id")
            
            # Find the anchor for this content in this script
            # 1. Try segments table (most accurate for processed scripts)
            anchor_id = get_anchor_id_by_ai_index(cursor, filename, ai_index)
            
            if not anchor_id:
                # 2. Fallback to direct anchor lookup by hash
                anchor_id = get_anchor_id_by_filename_and_hash(cursor, filename, content_hash)
            
            images = []
            downloaded_keywords = []
            
            if anchor_id:
                # Update last_used for all images attached to this anchor
                update_images_last_used(cursor, anchor_id)
                
                # Fetch active or pinned images
                rows = get_images_by_anchor(cursor, anchor_id)
                images = [{"path": r["file_path"], "source": r["source"], "keyword": r["keyword"]} for r in rows]
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
                # Strictly use the structured hierarchy: downloaded_images/script_name/segment_no/*/
                seg_id = segment.get("id", i)
                segment_base_dir = DOWNLOAD_DIR / script_stem / str(seg_id)
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
        response_format={"type": "json_object"},
        max_tokens=8192  # Increased for long scripts
    )
    return json.loads(response.choices[0].message.content)

@app.post("/api/process-script")
async def process_script(request: ProcessRequest):
    try:
        if request.source == "both":
            print(f"Processing script with BOTH sources: {request.filename}")
            with open("prompt_pinterest.txt", "r") as f:
                p_pin = f.read()
            with open("prompt_unsplash.txt", "r") as f:
                p_uns = f.read()
            
            prompt_pin = p_pin.replace("{script_text}", request.script_text)
            prompt_uns = p_uns.replace("{script_text}", request.script_text)
            
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
            print(f"Processing script with {request.source}: {request.filename}")
            prompt_file = "prompt_pinterest.txt" if request.source == "pinterest" else "prompt_unsplash.txt"
            with open(prompt_file, "r") as f:
                prompt_template = f.read()
            
            prompt = prompt_template.replace("{script_text}", request.script_text)
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
        
        # 1. Get or create script record
        script_id = get_script_id_by_filename(cursor, request.filename)
        if not script_id:
            script_id = create_script(cursor, request.filename)
        
        # Clear old segments for this script to avoid duplicates during re-processing
        delete_segments_for_script(cursor, script_id)

        # 2. Process segments into DB (anchor mapping)
        new_anchor_ids = set()
        for segment in segments:
            anchor_id = find_or_create_anchor(conn, script_id, segment.get("text", ""))
            new_anchor_ids.add(anchor_id)
            
            # Create segment view (the specific mapping of AI index to anchor for this version of the script)
            create_segment(cursor, script_id, anchor_id, segment.get("id"), segment.get("keywords", []))

        # 3. Orphan images linked to anchors no longer present in the updated script
        # This prevents images from "leaking" into segments where they no longer belong
        # while keeping them in the DB for potential reconciliation.
        orphan_unused_images(cursor, script_id, list(new_anchor_ids))
        
        conn.commit()
        conn.close()
        # -----------------

        return attach_images_to_segments(segments, request.filename)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/delete-images")
async def delete_images(request: DeleteImagesRequest):
    conn = get_db()
    cursor = conn.cursor()
    deleted_paths = []
    
    for path_str in request.image_paths:
        # Soft delete in DB using repo function
        if soft_delete_image(cursor, path_str) > 0:
            deleted_paths.append(path_str)
            
    conn.commit()
    conn.close()
    return {"deleted": deleted_paths}

@app.post("/api/download-keyword-images")
async def download_keyword_images(request: KeywordDownloadRequest):
    # 1. Get anchor_id and script_id from DB
    conn = get_db()
    cursor = conn.cursor()
    row = get_anchor_and_script_id(cursor, request.filename, request.segment_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Segment mapping not found in DB")

    anchor_id, script_id = row["anchor_id"], row["script_id"]
    conn.close()

    
    # 2. Scrape
    try:
        source_urls = [] # list of (url, source_name)
        total_downloaded_bytes = 0
        
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
                conn = get_db()
                cursor = conn.cursor()
                # Step 1: Pre-download URL Dedup
                existing = get_existing_image_by_url(cursor, url)
                
                if existing:
                    existing_path, existing_hash = existing["file_path"], existing["content_hash"]
                    insert_image(cursor, anchor_id, existing_path, request.keyword, url, img_source, existing_hash)
                    new_images.append({"path": existing_path, "source": img_source, "keyword": request.keyword})
                    conn.commit()
                    conn.close()
                    continue
                conn.close()

                # Step 2: Download and Content Hash Dedup
                img_uuid = generate_id()
                file_path = script_dir / f"{img_uuid}.jpg"
                path_str = file_path.as_posix()
                
                await loop.run_in_executor(None, download_image, url, file_path)
                
                if file_path.exists():
                    conn = get_db()
                    cursor = conn.cursor()
                    img_size = file_path.stat().st_size
                    total_downloaded_bytes += img_size
                    img_hash = get_image_hash(file_path)
                    
                    # Check for content hash match
                    match_path = get_image_by_content_hash(cursor, img_hash)
                    
                    if match_path:
                        # Found duplicate by content!
                        os.remove(file_path)
                        insert_image(cursor, anchor_id, match_path, request.keyword, url, img_source, img_hash)
                        new_images.append({"path": match_path, "source": img_source, "keyword": request.keyword})
                    else:
                        # Record in DB normally
                        insert_image(cursor, anchor_id, path_str, request.keyword, url, img_source, img_hash)
                        new_images.append({"path": path_str, "source": img_source, "keyword": request.keyword})
                    conn.commit()
                    conn.close()
                else:
                    print(f"Failed to download image from {url}")
            
            return {"images": new_images, "downloaded_bytes": total_downloaded_bytes}
            
        return {"images": [], "downloaded_bytes": 0}
    except Exception as e:
        print(f"Error scraping for keyword {request.keyword}: {type(e).__name__} - {e}")
        if conn: conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fetch")
async def fetch_api_images(request: ApiFetchRequest):
    """Fetch images from API-based providers (no browser needed)."""
    if request.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {request.provider}")

    # 1. Get anchor_id from DB (same lookup as download-keyword-images)
    conn = get_db()
    cursor = conn.cursor()
    row = get_anchor_and_script_id(cursor, request.filename, request.segment_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Segment not found in database. Process script first.")

    anchor_id, script_id = row["anchor_id"], row["script_id"]
    conn.close()

    # 2. Call provider search
    try:
        search_fn = PROVIDERS[request.provider]
        search_results = await search_fn(request.keyword, count=3)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Provider {request.provider} error: {e}")

    # 3. Download and store images
    new_images = []
    total_downloaded_bytes = 0
    script_dir = DOWNLOAD_DIR / script_id
    script_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http_client:
        for result in search_results:
            source_url = result["url"]

            conn = get_db()
            cursor = conn.cursor()
            # Pre-download URL dedup
            existing = get_existing_image_by_url(cursor, source_url)

            if existing:
                existing_path, existing_hash = existing["file_path"], existing["content_hash"]
                insert_image(cursor, anchor_id, existing_path, request.keyword, source_url, 
                             result["source"], existing_hash, request.provider, "api")
                new_images.append({"path": existing_path, "source": result["source"], "keyword": request.keyword})
                conn.commit()
                conn.close()
                continue
            conn.close()

            # Download the image
            img_uuid = generate_id()
            # Determine file extension from URL or default to .png
            ext = ".png"
            if ".jpg" in source_url or ".jpeg" in source_url:
                ext = ".jpg"
            elif ".svg" in source_url:
                ext = ".svg"
            file_path = script_dir / f"{img_uuid}{ext}"
            path_str = file_path.as_posix()

            try:
                resp = await http_client.get(source_url)
                resp.raise_for_status()
                img_data = resp.content
                file_path.write_bytes(img_data)
            except Exception as e:
                print(f"Failed to download {source_url}: {type(e).__name__} - {e}")
                continue

            if file_path.exists():
                conn = get_db()
                cursor = conn.cursor()
                img_size = file_path.stat().st_size
                total_downloaded_bytes += img_size
                img_hash = get_image_hash(file_path)

                # Content hash dedup
                match_path = get_image_by_content_hash(cursor, img_hash)

                if match_path:
                    os.remove(file_path)
                    insert_image(cursor, anchor_id, match_path, request.keyword, source_url,
                                 result["source"], img_hash, request.provider, "api")
                    new_images.append({"path": match_path, "source": result["source"], "keyword": request.keyword})
                else:
                    insert_image(cursor, anchor_id, path_str, request.keyword, source_url,
                                 result["source"], img_hash, request.provider, "api")
                    new_images.append({"path": path_str, "source": result["source"], "keyword": request.keyword})
                conn.commit()
                conn.close()

    return {"images": new_images, "downloaded_bytes": total_downloaded_bytes}

@app.post("/api/pin-image")
async def pin_image(request: PinImageRequest):
    conn = get_db()
    cursor = conn.cursor()

    update_image_pinned_status(cursor, request.image_path, request.pin, request.note)

    conn.commit()
    conn.close()
    return {"status": 'pinned' if request.pin else 'active'}
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
