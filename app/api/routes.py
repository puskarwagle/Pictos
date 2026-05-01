import json
import asyncio
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.core.config import SCRIPTS_DIR, RESPONSES_DIR, BASE_DIR
from app.db.session import get_db
from app.db.repository import (
    get_script_id_by_filename, create_script, delete_segments_for_script,
    create_segment, orphan_unused_images, soft_delete_image,
    get_anchor_and_script_id, update_image_pinned_status,
    hash_content, get_anchor_by_hash, get_anchors_for_script, 
    update_anchor_content, create_anchor
)
import difflib
from app.models.api_models import (
    ProcessRequest, DownloadRequest, KeywordDownloadRequest,
    DeleteImagesRequest, ApiFetchRequest, PinImageRequest
)
from app.services.ai_service import ai_service
from app.services.image_service import (
    attach_images_to_segments, BROWSER_SEMAPHORE, process_and_store_image
)
from app.services.providers import PROVIDERS, API_PROVIDERS
from app.services.providers.pinterest_scraper import get_pinterest_images_async
from app.services.providers.unsplash_scraper import get_unsplash_images_async

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

router = APIRouter()

@router.get("/api/scripts")
async def list_scripts():
    scripts = [f.name for f in SCRIPTS_DIR.glob("*.md")]
    return scripts

@router.get("/api/script/{filename}")
async def get_script(filename: str):
    script_path = SCRIPTS_DIR / filename
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    with open(script_path, "r") as f:
        return {"content": f.read()}

@router.get("/api/script/{filename}/response")
async def get_script_response(filename: str):
    stem = Path(filename).stem
    response_file = RESPONSES_DIR / f"{stem}.json"
    if not response_file.exists():
        return []
    with open(response_file, "r") as f:
        data = json.load(f)
        segments = data.get("segments", data) if isinstance(data, dict) else data
        return attach_images_to_segments(segments, filename)

@router.post("/api/process-script")
async def process_script(request: ProcessRequest):
    try:
        # process_script now always uses high-density mapping internally
        result = await ai_service.process_script(request.script_text, request.source)

        # Save the AI response to a file (legacy fallback)
        stem = Path(request.filename).stem
        response_file = RESPONSES_DIR / f"{stem}.json"
        with open(response_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        segments = result.get("segments", [])
        
        # --- DB Update ---
        conn = get_db()
        cursor = conn.cursor()
        
        script_id = get_script_id_by_filename(cursor, request.filename)
        if not script_id:
            script_id = create_script(cursor, request.filename)
        
        delete_segments_for_script(cursor, script_id)

        new_anchor_ids = set()
        for segment in segments:
            anchor_id = find_or_create_anchor(conn, script_id, segment.get("text", ""))
            new_anchor_ids.add(anchor_id)
            create_segment(cursor, script_id, anchor_id, segment.get("id"), segment.get("keywords", []))

        orphan_unused_images(cursor, script_id, list(new_anchor_ids))
        
        conn.commit()
        conn.close()

        return attach_images_to_segments(segments, request.filename)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/delete-images")
async def delete_images(request: DeleteImagesRequest):
    conn = get_db()
    cursor = conn.cursor()
    deleted_paths = []
    for path_str in request.image_paths:
        if soft_delete_image(cursor, path_str) > 0:
            deleted_paths.append(path_str)
    conn.commit()
    conn.close()
    return {"deleted": deleted_paths}

@router.post("/api/download-keyword-images")
async def download_keyword_images(request: KeywordDownloadRequest):
    conn = get_db()
    cursor = conn.cursor()
    row = get_anchor_and_script_id(cursor, request.filename, request.segment_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Segment mapping not found in DB")

    anchor_id, script_id = row["anchor_id"], row["script_id"]
    conn.close()

    try:
        source_urls = []
        async with BROWSER_SEMAPHORE:
            if request.source == "pinterest":
                urls = await get_pinterest_images_async(request.keyword, 3, True)
                source_urls = [(u, "pinterest") for u in urls]
            elif request.source == "unsplash":
                urls = await get_unsplash_images_async(request.keyword, 3, True)
                source_urls = [(u, "unsplash") for u in urls]
            elif request.source == "both":
                urls_pin = await get_pinterest_images_async(request.keyword, 2, True)
                urls_uns = await get_unsplash_images_async(request.keyword, 2, True)
                source_urls = [(u, "pinterest") for u in urls_pin] + [(u, "unsplash") for u in urls_uns]
        
        new_images = []
        total_downloaded_bytes = 0
        if source_urls:
            for url, img_source in source_urls:
                res = await process_and_store_image(url, anchor_id, script_id, request.keyword, img_source)
                if res:
                    new_images.append({"path": res["path"], "source": res["source"], "keyword": res["keyword"]})
                    total_downloaded_bytes += res.get("size", 0)
            
            return {"images": new_images, "downloaded_bytes": total_downloaded_bytes}
            
        return {"images": [], "downloaded_bytes": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/fetch")
async def fetch_api_images(request: ApiFetchRequest):
    if request.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {request.provider}")

    conn = get_db()
    cursor = conn.cursor()
    row = get_anchor_and_script_id(cursor, request.filename, request.segment_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Segment not found in database.")

    anchor_id, script_id = row["anchor_id"], row["script_id"]
    conn.close()

    try:
        search_fn = PROVIDERS[request.provider]
        search_results = await search_fn(request.keyword, count=3)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Provider {request.provider} error: {e}")

    new_images = []
    total_downloaded_bytes = 0
    for result in search_results:
        res = await process_and_store_image(
            result["url"], anchor_id, script_id, request.keyword, 
            result["source"], request.provider, "api"
        )
        if res:
            new_images.append({"path": res["path"], "source": res["source"], "keyword": res["keyword"]})
            total_downloaded_bytes += res.get("size", 0)

    return {"images": new_images, "downloaded_bytes": total_downloaded_bytes}

@router.post("/api/pin-image")
async def pin_image(request: PinImageRequest):
    conn = get_db()
    cursor = conn.cursor()
    update_image_pinned_status(cursor, request.image_path, request.pin, request.note)
    conn.commit()
    conn.close()
    return {"status": 'pinned' if request.pin else 'active'}

@router.get("/", response_class=HTMLResponse)
async def get_index():
    template_path = BASE_DIR / "app/templates/index.html"
    with open(template_path, "r") as f:
        return f.read()
