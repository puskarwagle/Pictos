# Pictos Code Context for Clip Quality Improvements

This file contains the core code files driving keyword extraction, YouTube clip searching/transcript matching, AI prompts, and route parameter passing to help analyze and improve clip quality.

---

## 1. File: `app/services/youtube_service.py`

This is the core of how clips are found, searched via `yt-dlp`, and matched using transcript alignment.

```python
"""
YouTube Video Clip Service — search YouTube and match transcripts.
Uses yt-dlp for video search/metadata and youtube-transcript-api for transcript matching.
"""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from app.core.config import CLIP_DURATION

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _search_youtube_sync(keyword: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Search YouTube for videos matching a keyword.
    Returns metadata for up to `count` videos.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
        'ignoreerrors': True,
    }

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch{count}:{keyword}"
            info = ydl.extract_info(search_query, download=False)

            if not info or 'entries' not in info:
                return []

            for entry in info['entries']:
                if entry is None:
                    continue
                video_id = entry.get('id', '')
                duration = entry.get('duration', 0)
                view_count = entry.get('view_count', 0)

                # 2. Filter out very short (<30s) or very long (>20min) videos
                if duration and (duration < 30 or duration > 1200):
                    continue

                results.append({
                    'video_id': video_id,
                    'title': entry.get('title', 'Untitled'),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail': entry.get('thumbnail') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    'duration': duration,
                    'channel': entry.get('uploader', 'Unknown'),
                    'view_count': view_count,
                })
    except Exception as e:
        logger.error(f"YouTube search failed for '{keyword}': {e}")

    return results


def _get_transcript_sync(video_id: str) -> Optional[List[Dict]]:
    """Fetch transcript for a YouTube video. Returns None if unavailable."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Prefer English, fall back to any available
        try:
            transcript = transcript_list.find_transcript(['en'])
        except Exception:
            # Try auto-generated or any language
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except Exception:
                # Get whatever is available
                for t in transcript_list:
                    transcript = t
                    break
                else:
                    return None

        return transcript.fetch()
    except Exception as e:
        logger.debug(f"No transcript for {video_id}: {e}")
        return None


def _score_transcript_match(transcript: List[Dict], keyword: str) -> float:
    """
    Score how well a transcript matches a keyword.
    Returns 0.0–1.0. Higher = better match.
    """
    keyword_lower = keyword.lower()
    keyword_words = [w for w in keyword_lower.split() if len(w) > 3]
    full_text = " ".join(e.get('text', '') for e in transcript).lower()

    if keyword_lower in full_text:
        return 1.0  # Exact phrase match

    if not keyword_words:
        return 0.0

    matched = sum(1 for w in keyword_words if w in full_text)
    return matched / len(keyword_words)


def _find_keyword_in_transcript(
    transcript: List[Dict],
    keyword: str,
    clip_duration: int = CLIP_DURATION,
    max_matches: int = 3
) -> List[Dict[str, Any]]:
    """
    Find timestamps in transcript where the keyword/phrase appears.
    Returns clip segments centered on the match.
    """
    keyword_lower = keyword.lower()
    keyword_words = [w for w in keyword_lower.split() if len(w) > 3]
    matches = []

    for i, entry in enumerate(transcript):
        text = entry.get('text', '').lower()

        # Require exact phrase OR ALL significant words present — not just any one
        exact_hit = keyword_lower in text
        all_words_hit = keyword_words and all(w in text for w in keyword_words)

        if exact_hit or all_words_hit:
            # Center the clip on the match (not just offset from start)
            start = max(0, entry['start'] - clip_duration * 0.4)
            end = entry['start'] + clip_duration * 0.6

            # Build a snippet from surrounding transcript entries
            snippet_parts = []
            for j in range(max(0, i - 1), min(len(transcript), i + 3)):
                snippet_parts.append(transcript[j].get('text', ''))
            snippet = ' '.join(snippet_parts)

            matches.append({
                'timestamp_start': round(start, 1),
                'timestamp_end': round(end, 1),
                'transcript_snippet': snippet[:200],
                'exact': exact_hit,  # flag for ranking
            })

            if len(matches) >= max_matches:
                break

    return matches


async def search_youtube_clips(keyword: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Search YouTube for videos matching a keyword.
    Async wrapper around the sync yt-dlp call.
    """
    return await asyncio.to_thread(_search_youtube_sync, keyword, count)


async def get_transcript(video_id: str) -> Optional[List[Dict]]:
    """Fetch transcript for a video. Async wrapper."""
    return await asyncio.to_thread(_get_transcript_sync, video_id)


async def search_and_match(
    keyword: str,
    count: int = 3,
    search_queries: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Combined search: find YouTube videos, check transcripts for keyword relevance,
    and return ranked clip results with timestamps.

    This is the main provider function registered in PROVIDERS.
    Returns results in the same shape as the old image providers for compatibility.
    """
    # Clean the primary keyword
    cleaned_keyword = keyword
    if ":" in cleaned_keyword:
        parts = cleaned_keyword.split(":", 1)
        if parts[0].lower() in ["youtube", "pinterest", "unsplash", "google", "image"]:
            cleaned_keyword = parts[1].strip()

    # Determine which queries to search
    if search_queries:
        queries = search_queries
    else:
        queries = [cleaned_keyword]

    all_videos = []
    seen_ids = set()
    for q in queries:
        # Clean query just in case it has prefix
        cleaned_q = q
        if ":" in cleaned_q:
            parts = cleaned_q.split(":", 1)
            if parts[0].lower() in ["youtube", "pinterest", "unsplash", "google", "image"]:
                cleaned_q = parts[1].strip()

        results = await search_youtube_clips(cleaned_q, count=count + 2)
        for v in results:
            if v['video_id'] not in seen_ids:
                seen_ids.add(v['video_id'])
                all_videos.append(v)

    # Score each video by transcript quality
    scored = []
    for video in all_videos:
        video_id = video['video_id']
        transcript = await get_transcript(video_id)

        if not transcript:
            continue  # ← fix 3: skip no-transcript videos entirely

        score = _score_transcript_match(transcript, cleaned_keyword)
        if score == 0.0:
            continue  # No meaningful match, skip

        matches = _find_keyword_in_transcript(transcript, cleaned_keyword, max_matches=1)
        if not matches:
            continue

        match = matches[0]
        scored.append({
            'score': score + (1.0 if match['exact'] else 0.0),  # exact phrase = bonus
            'video_id': video_id,
            'title': video['title'],
            'url': video['url'],
            'thumbnail': video['thumbnail'],
            'timestamp_start': match['timestamp_start'],
            'timestamp_end': match['timestamp_end'],
            'transcript_snippet': match['transcript_snippet'],
            'channel': video.get('channel', 'Unknown'),
            'source': 'youtube',
        })

    # Sort by score, return top `count`
    scored.sort(key=lambda x: x['score'], reverse=True)
    for r in scored:
        r.pop('score', None)  # Don't leak internal score to frontend

    return scored[:count]
```

---

## 2. File: `app/services/ai_service.py`

This handles global vibe analysis, chunking, and calling DeepSeek to map scripts to dense keywords.

```python
import json
import asyncio
import logging
import datetime
from typing import List, Dict, Any
from openai import OpenAI
from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROMPTS_DIR, RESPONSES_DIR

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=300.0
        )

    def _repair_json(self, json_str: str) -> str:
        """Attempts to repair truncated or malformed JSON from AI."""
        json_str = json_str.strip()
        if not json_str:
            return "{}"
        
        # If it's already valid, return it
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            pass

        # Track state to close properly
        stack = []
        in_string = False
        escaped = False
        
        fixed_str = ""
        for i, char in enumerate(json_str):
            if char == '"' and not escaped:
                in_string = not in_string
            
            if not in_string:
                if char == '{':
                    stack.append('}')
                elif char == '[':
                    stack.append(']')
                elif char == '}':
                    if stack and stack[-1] == '}':
                        stack.pop()
                elif char == ']':
                    if stack and stack[-1] == ']':
                        stack.pop()
            
            if char == '\\' and not escaped:
                escaped = True
            else:
                escaped = False
            fixed_str += char

        # If we are inside a string at the end, close it
        if in_string:
            fixed_str += '"'
        
        # Iteratively remove trailing problematic characters
        while True:
            fixed_str = fixed_str.rstrip()
            if not fixed_str:
                break
            
            last_char = fixed_str[-1]
            
            # Remove trailing delimiters that have no following value
            if last_char in (',', ':', '{', '['):
                if last_char in ('{', '['):
                    if stack: stack.pop()
                fixed_str = fixed_str[:-1]
                continue
            
            # If it ends with a quote, check if it's a key without a colon
            # or a value that we just closed.
            if last_char == '"':
                # Find the start of this string
                start_quote = -1
                for j in range(len(fixed_str) - 2, -1, -1):
                    if fixed_str[j] == '"':
                        # Count backslashes before this quote to handle escapes
                        temp_bs = 0
                        for k in range(j-1, -1, -1):
                            if fixed_str[k] == '\\': temp_bs += 1
                            else: break
                        if temp_bs % 2 == 0:
                            start_quote = j
                            break
                
                if start_quote != -1:
                    before_str = fixed_str[:start_quote].rstrip()
                    # A string is a KEY if it's preceded by { or ,
                    # A string is a VALUE if it's preceded by : or [
                    if before_str and before_str[-1] in ('{', ','):
                        # It could be a key OR a value in an array.
                        # If the stack says we're in an object, it's a key.
                        if stack and stack[-1] == '}':
                            # This is a key. Since no colon follows, it's truncated.
                            fixed_str = before_str
                            continue
            
            break

        # Close all open braces/brackets
        while stack:
            fixed_str += stack.pop()
            
        return fixed_str

    async def call_ai(self, prompt: str) -> Dict[str, Any]:
        """Helper to call DeepSeek AI asynchronously."""
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts visual keywords from scripts. Output strictly valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=8192
            )
            content = response.choices[0].message.content
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                # Save problematic response for debugging
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = RESPONSES_DIR / f"failed_response_{timestamp}.json"
                with open(debug_file, "w") as f:
                    f.write(content)
                logger.info(f"Saved failed response to {debug_file}")
                
                # Try to repair
                repaired_content = self._repair_json(content)
                try:
                    return json.loads(repaired_content)
                except json.JSONDecodeError as e2:
                    logger.error(f"Repair failed: {e2}")
                    logger.error(f"Repaired content: {repaired_content}")
                    raise
                
        except Exception as e:
            logger.error(f"Error calling AI: {e}")
            raise

    def get_prompt(self, source: str) -> str:
        """Loads a prompt template from the resources directory."""
        filename = f"prompt_{source}.txt"
        prompt_path = PROMPTS_DIR / filename
        if not prompt_path.exists():
            # Fallback to general dense mapping if specific prompt doesn't exist
            prompt_path = PROMPTS_DIR / "prompt_dense_mapping.txt"
        
        with open(prompt_path, "r") as f:
            return f.read()

    def load_manifest(self) -> str:
        """Loads the providers manifest as a string for prompting."""
        manifest_path = PROMPTS_DIR.parent / "providers_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r") as f:
                return f.read()
        return "[]"

    def _chunk_script(self, script_text: str, max_chars: int = 1500) -> List[str]:
        """Splits a long script into manageable chunks for AI processing."""
        if len(script_text) <= max_chars:
            return [script_text]

        chunks = []
        remaining = script_text

        while remaining:
            if len(remaining) <= max_chars:
                chunks.append(remaining)
                break

            # Try to find the best split point within the max_chars limit
            search_window = remaining[:max_chars]
            
            # 1. Try double newline (paragraph)
            split_idx = search_window.rfind("\n\n")
            
            # 2. Try single newline (sentence)
            if split_idx == -1:
                split_idx = search_window.rfind("\n")
            
            # 3. Try space (word)
            if split_idx == -1:
                split_idx = search_window.rfind(" ")
            
            # 4. Hard cut (if no separators found, which is unlikely)
            if split_idx == -1:
                split_idx = max_chars

            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx:].strip()

        return chunks

    async def process_script(self, script_text: str, source: str = "dense") -> Dict[str, Any]:
        """Processes a script using AI to extract segments and keywords."""
        return await self.process_script_dense(script_text)

    async def process_script_dense(self, script_text: str) -> Dict[str, Any]:
        """Multi-step high-density visual mapping pipeline with parallel chunking."""
        # 1. Vibe Analysis (Full script for global context)
        vibe_prompt = self.get_prompt("vibe_analysis").replace("{script_text}", script_text)
        vibe_analysis = await self.call_ai(vibe_prompt)
        
        # 2. Chunking
        chunks = self._chunk_script(script_text, max_chars=1500)
        logger.info(f"Split script into {len(chunks)} chunks for processing.")
        
        # 3. Concurrent Dense Mapping
        manifest = self.load_manifest()
        mapping_template = self.get_prompt("dense_mapping")\
            .replace("{providers_manifest}", manifest)\
            .replace("{vibe_analysis}", json.dumps(vibe_analysis, indent=2))
        
        tasks = []
        for chunk in chunks:
            prompt = mapping_template.replace("{script_text}", chunk)
            tasks.append(self.call_ai(prompt))
        
        # Gather all chunk results
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. Merge and Renumber
        all_segments = []
        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                logger.error(f"Chunk {i} failed: {result}")
                continue
            
            segments = result.get("segments", [])
            all_segments.extend(segments)
        
        # Re-assign IDs and post-process
        for idx, seg in enumerate(all_segments):
            seg["id"] = idx + 1
            
            # Transform anchors into UI-compatible keywords
            all_keywords = []
            for anchor in seg.get("anchors", []):
                provider = anchor.get("provider", "pinterest")
                queries = anchor.get("search_queries") or anchor.get("keywords") or []
                keywords = [f"{provider}:{q}" for q in queries]
                all_keywords.extend(keywords)
                all_keywords.append("|")
            
            if all_keywords and all_keywords[-1] == "|":
                all_keywords.pop()
                
            seg["keywords"] = all_keywords
            seg["text"] = seg.get("full_text", "")
            
        return {"segments": all_segments, "vibe": vibe_analysis}

    async def translate_keyword(self, keyword: str) -> str:
        """Translates a keyword to English if it's not already."""
        prompt = f"Translate the following keyword or phrase to English. If it is already in English, return it exactly as is. Output ONLY the translated string, no quotes, no extra text:\n\n{keyword}"
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a translation assistant. Provide only the direct translation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error translating keyword: {e}")
            return keyword

ai_service = AIService()
```

---

## 3. File: `resources/prompts/prompt_dense_mapping.txt`

This is the DeepSeek prompt structure driving how visual anchors and keyword selections are selected for the YouTube provider.

```text
You are a Visual Research Lead for a high-production video team. 
Your job is to map a script to a DENSE sequence of visual anchors for YouTube video clips.

### CONTEXT:
The user wants a "High-Retention" style where clips change frequently to keep the viewer engaged.
Sometimes there are multiple clips for a single sentence.

### TOOLS (PROVIDERS):
{providers_manifest}

### INSTRUCTIONS:
1. **Read the Script and the Vibe Analysis provided.**
2. **Create Visual Anchors:** 
    - Identify specific words or short phrases (anchors) that should trigger a new video clip.
    - Aim for high density: 1 clip every 4-8 words for fast sections, 1 every 10-15 for slow ones.
3. **Provider:** Always use the "youtube" provider from the manifest.
4. **Generate Search Queries:** Create 2 English search queries for the YouTube provider that would return relevant explanatory b-roll, footage, or animations.

### SEARCH QUERY RULES:
- Each query must be a complete YouTube search string, ready to paste into the search bar.
- Match query style to content type — don't use "documentary" for animation concepts, don't use "3D animation" for real historical places.
- 2 queries per anchor. Make them meaningfully different (one specific, one broader).
- Queries must be in English regardless of script language.

### OUTPUT FORMAT:
Return ONLY a valid JSON object:
{
  "segments": [
    {
      "id": 1,
      "full_text": "The full sentence or paragraph being processed",
      "anchors": [
        {
          "text": "specific word/phrase",
          "provider": "youtube",
          "search_queries": [
            "Ancient Rome colosseum aerial drone footage",
            "Roman empire documentary ruins cinematic"
          ]
        }
      ]
    }
  ]
}

### VIBE ANALYSIS (Global context for the whole video):
{vibe_analysis}

### SCRIPT CHUNK (Process ONLY this part of the text):
{script_text}
```

---

## 4. File: `resources/prompts/prompt_vibe_analysis.txt`

This prompt analyzes the global context, vibe, recommended density, and visual theme instructions before script chunking occurs.

```text
You are a Master Video Editor and Content Strategist specializing in high-retention "faceless" YouTube videos.
Your goal is to analyze a script and determine its "Visual Pacing" and "Thematic Tone."

I will give you a script in Nepali or Romanized Nepali.

### TASK:
1. **Identify the Core Subject:** (e.g., Medical Science, Ancient History, Tech Tutorial).
2. **Determine the Vibe:** (e.g., Urgent and Fast-paced, Calm and Educational, Dark and Mysterious).
3. **Pacing Analysis:** 
    - Identify "High Energy" sections that need rapid-fire images (1-2 seconds per image).
    - Identify "Deep Dive" sections that need a single, complex diagram or detailed shot to stay on screen (5-10 seconds).
4. **Keyword Language:** Confirm if keywords should be strictly English (standard) or if local context is needed.

### OUTPUT FORMAT:
Return ONLY a valid JSON object:
{
  "subject": "string",
  "vibe": "string",
  "overall_pacing": "fast | moderate | slow",
  "pacing_notes": [
    {
      "text_snippet": "start of sentence...",
      "recommended_density": "high | low",
      "reason": "why it needs this density"
    }
  ],
  "visual_theme_instructions": "General instructions for the next AI agent on what kind of color palette or style to look for."
}

SCRIPT:
{script_text}
```

---

## 5. File: `app/api/routes.py`

This defines our API endpoints showing how search params and segments are passed end-to-end (e.g., in `/api/process-script` and `/api/fetch-clips`).

```python
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

@router.get("/api/script/{filename}/response")
async def get_script_response(filename: str):
    stem = Path(filename).stem
    response_file = RESPONSES_DIR / f"{stem}.json"
    if not response_file.exists():
        raise HTTPException(status_code=404, detail="No cached response found")
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
```
