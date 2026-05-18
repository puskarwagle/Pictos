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
    keyword_lower = keyword.lower().strip()
    keyword_words = [w for w in keyword_lower.split() if len(w) > 3]
    matches = []

    if not transcript:
        return []

    # 1. Try Exact Phrase Match across consecutive entries using character mapping
    full_text = ""
    entry_boundaries = []
    for i, entry in enumerate(transcript):
        text = entry.get('text', '').lower().strip()
        start_char = len(full_text)
        full_text += text + " "
        end_char = len(full_text)
        entry_boundaries.append((start_char, end_char, i))

    match_idx = full_text.find(keyword_lower)
    if match_idx != -1:
        # Find which entry contains the start of the match
        matched_entry_idx = 0
        for start_char, end_char, entry_idx in entry_boundaries:
            if start_char <= match_idx < end_char:
                matched_entry_idx = entry_idx
                break
        
        entry = transcript[matched_entry_idx]
        start = max(0, entry['start'] - clip_duration * 0.4)
        end = entry['start'] + clip_duration * 0.6
        
        # Build snippet
        snippet_parts = []
        for j in range(max(0, matched_entry_idx - 1), min(len(transcript), matched_entry_idx + 3)):
            snippet_parts.append(transcript[j].get('text', ''))
        snippet = ' '.join(snippet_parts)

        return [{
            'timestamp_start': round(start, 1),
            'timestamp_end': round(end, 1),
            'transcript_snippet': snippet[:200],
            'exact': True,
        }]

    # 2. Try Exact Phrase Match for individual entries (fallback/redundancy)
    for i, entry in enumerate(transcript):
        text = entry.get('text', '').lower()
        if keyword_lower in text:
            start = max(0, entry['start'] - clip_duration * 0.4)
            end = entry['start'] + clip_duration * 0.6
            
            snippet_parts = []
            for j in range(max(0, i - 1), min(len(transcript), i + 3)):
                snippet_parts.append(transcript[j].get('text', ''))
            snippet = ' '.join(snippet_parts)

            matches.append({
                'timestamp_start': round(start, 1),
                'timestamp_end': round(end, 1),
                'transcript_snippet': snippet[:200],
                'exact': True,
            })
            if len(matches) >= max_matches:
                return matches

    # 3. Try Sliding Window Word Matching (fallback for long phrases / disjoint matches)
    if keyword_words:
        window_size = 4
        best_window_idx = -1
        best_window_matches = 0
        
        for i in range(len(transcript) - window_size + 1):
            window_entries = transcript[i : i + window_size]
            window_text = " ".join(e.get('text', '') for e in window_entries).lower()
            
            matches_count = sum(1 for w in keyword_words if w in window_text)
            if matches_count > best_window_matches:
                best_window_matches = matches_count
                best_window_idx = i

        # If we matched at least 50% of the significant words, we consider it a hit!
        min_required_matches = max(1, len(keyword_words) // 2)
        if best_window_matches >= min_required_matches and best_window_idx != -1:
            entry = transcript[best_window_idx]
            start = max(0, entry['start'] - clip_duration * 0.4)
            end = entry['start'] + clip_duration * 0.6
            
            snippet_parts = []
            for j in range(max(0, best_window_idx - 1), min(len(transcript), best_window_idx + window_size + 1)):
                snippet_parts.append(transcript[j].get('text', ''))
            snippet = ' '.join(snippet_parts)

            matches.append({
                'timestamp_start': round(start, 1),
                'timestamp_end': round(end, 1),
                'transcript_snippet': snippet[:200],
                'exact': False,
            })

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
        transcript = None
        try:
            transcript = await get_transcript(video_id)
        except Exception as e:
            logger.debug(f"Error getting transcript: {e}")

        matches = []
        score = 0.0
        if transcript:
            score = _score_transcript_match(transcript, cleaned_keyword)
            matches = _find_keyword_in_transcript(transcript, cleaned_keyword, max_matches=1)

        if matches:
            match = matches[0]
            scored.append({
                'score': score + 2.0 + (1.0 if match['exact'] else 0.0),  # highest priority: exact or sliding window matches
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
        else:
            # Fallback: No transcript or no match, but video was returned by YouTube search.
            # Start at 0 seconds, rank lower than matched videos but above nothing!
            scored.append({
                'score': 1.0,  # lower priority fallback
                'video_id': video_id,
                'title': video['title'],
                'url': video['url'],
                'thumbnail': video['thumbnail'],
                'timestamp_start': 0,
                'timestamp_end': CLIP_DURATION,
                'transcript_snippet': '[No precise transcript match found - playing from start]',
                'channel': video.get('channel', 'Unknown'),
                'source': 'youtube',
            })

    # Sort by score, return top `count`
    scored.sort(key=lambda x: x['score'], reverse=True)
    for r in scored:
        r.pop('score', None)  # Don't leak internal score to frontend

    return scored[:count]

