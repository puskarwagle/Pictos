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
    create_segment, orphan_unused_images, soft_delete_clip,
    get_anchor_and_script_id, update_clip_pinned_status,
    hash_content, get_anchor_by_hash, get_anchors_for_script, 
    update_anchor_content, create_anchor, orphan_unused_clips
)
import difflib
from app.models.api_models import (
    ProcessRequest, ClipFetchRequest,
    DeleteClipsRequest, PinClipRequest, TranslateRequest, SaveSegmentsRequest
)
from app.services.ai_service import ai_service
from app.services.clip_service import attach_clips_to_segments, process_and_store_clip
from app.services.youtube_service import search_and_match

def find_or_create_anchor(conn, script_id: str, content: str):
    """
    Finds an existing text anchor for a given script or creates a new one.
    Implements a two-stage matching process:
    1. Exact Match: Checks if the content hash already exists for this script.
    2. Fuzzy Match: Uses difflib to find existing anchors with >92% similarity,
       allowing for minor edits in the text editor without losing clip associations.
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

@router.post("/api/script/{filename}")
async def save_script(filename: str, request: dict):
    script_path = SCRIPTS_DIR / filename
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    with open(script_path, "w") as f:
        f.write(request.get("content", ""))
    return {"status": "success"}

@router.get("/api/script/{filename}/response")
async def get_script_response(filename: str):
    stem = Path(filename).stem
    response_file = RESPONSES_DIR / f"{stem}.json"
    if not response_file.exists():
        return []
    with open(response_file, "r") as f:
        data = json.load(f)
        segments = data.get("segments", data) if isinstance(data, dict) else data
        return attach_clips_to_segments(segments, filename)

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
        orphan_unused_clips(cursor, script_id, list(new_anchor_ids))
        
        conn.commit()
        conn.close()

        return attach_clips_to_segments(segments, request.filename)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/delete-clips")
async def delete_clips(request: DeleteClipsRequest):
    conn = get_db()
    cursor = conn.cursor()
    deleted_ids = []
    for clip_id in request.clip_ids:
        if soft_delete_clip(cursor, clip_id) > 0:
            deleted_ids.append(clip_id)
    conn.commit()
    conn.close()
    return {"deleted": deleted_ids}

@router.post("/api/fetch-clips")
async def fetch_clips(request: ClipFetchRequest):
    """Fetch YouTube clips for a keyword in a specific segment."""
    conn = get_db()
    cursor = conn.cursor()
    row = get_anchor_and_script_id(cursor, request.filename, request.segment_id)
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Segment not found in database.")

    anchor_id, script_id = row["anchor_id"], row["script_id"]
    conn.close()

    try:
        # Search YouTube and match transcripts
        clip_results = await search_and_match(request.keyword, count=3)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"YouTube search error: {e}")

    new_clips = []
    for clip_data in clip_results:
        res = await process_and_store_clip(
            clip_data, anchor_id, script_id, request.keyword
        )
        if res:
            new_clips.append(res)

    return {"clips": new_clips}

@router.post("/api/pin-clip")
async def pin_clip(request: PinClipRequest):
    conn = get_db()
    cursor = conn.cursor()
    update_clip_pinned_status(cursor, request.clip_id, request.pin, request.note)
    conn.commit()
    conn.close()
    return {"status": 'pinned' if request.pin else 'active'}

@router.post("/api/translate")
async def translate_keyword(request: TranslateRequest):
    translated = await ai_service.translate_keyword(request.keyword)
    return {"translated": translated}

@router.post("/api/save-segments")
async def save_segments(request: SaveSegmentsRequest):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        script_id = get_script_id_by_filename(cursor, request.filename)
        if not script_id:
            script_id = create_script(cursor, request.filename)
            
        delete_segments_for_script(cursor, script_id)
        
        new_anchor_ids = set()
        segments_data = []
        for segment in request.segments:
            seg_dict = segment.dict()
            segments_data.append(seg_dict)
            
            anchor_id = find_or_create_anchor(conn, script_id, seg_dict.get("text", ""))
            new_anchor_ids.add(anchor_id)
            create_segment(cursor, script_id, anchor_id, seg_dict.get("id"), seg_dict.get("keywords", []))
            
        orphan_unused_images(cursor, script_id, list(new_anchor_ids))
        orphan_unused_clips(cursor, script_id, list(new_anchor_ids))
        conn.commit()
        conn.close()
        
        # Save to JSON
        stem = Path(request.filename).stem
        response_file = RESPONSES_DIR / f"{stem}.json"
        
        vibe_data = None
        if response_file.exists():
            with open(response_file, "r", encoding="utf-8") as f:
                try:
                    old_data = json.load(f)
                    vibe_data = old_data.get("vibe") if isinstance(old_data, dict) else None
                except:
                    pass
        
        out_data = {"segments": segments_data}
        if vibe_data:
            out_data["vibe"] = vibe_data
            
        with open(response_file, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=4, ensure_ascii=False)
            
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_class=HTMLResponse)
async def get_index():
    template_path = BASE_DIR / "app/templates/index.html"
    with open(template_path, "r") as f:
        return f.read()
