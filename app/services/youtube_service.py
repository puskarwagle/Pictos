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
                results.append({
                    'video_id': video_id,
                    'title': entry.get('title', 'Untitled'),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail': entry.get('thumbnail') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    'duration': entry.get('duration', 0),
                    'channel': entry.get('uploader', 'Unknown'),
                    'view_count': entry.get('view_count', 0),
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
    keyword_words = keyword_lower.split()
    matches = []

    for i, entry in enumerate(transcript):
        text = entry.get('text', '').lower()

        # Check if keyword appears in this transcript segment
        if keyword_lower in text or any(word in text for word in keyword_words if len(word) > 3):
            start = max(0, entry['start'] - clip_duration / 4)
            end = entry['start'] + clip_duration

            # Build a snippet from surrounding transcript entries
            snippet_parts = []
            for j in range(max(0, i - 1), min(len(transcript), i + 3)):
                snippet_parts.append(transcript[j].get('text', ''))
            snippet = ' '.join(snippet_parts)

            matches.append({
                'timestamp_start': round(start, 1),
                'timestamp_end': round(end, 1),
                'transcript_snippet': snippet[:200],
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


async def search_and_match(keyword: str, count: int = 3) -> List[Dict[str, Any]]:
    """
    Combined search: find YouTube videos, check transcripts for keyword relevance,
    and return ranked clip results with timestamps.

    This is the main provider function registered in PROVIDERS.
    Returns results in the same shape as the old image providers for compatibility.
    """
    videos = await search_youtube_clips(keyword, count=count + 2)  # fetch extra in case some lack transcripts

    results = []
    for video in videos:
        if len(results) >= count:
            break

        video_id = video['video_id']
        transcript = await get_transcript(video_id)

        if transcript:
            # Find matching timestamps
            matches = _find_keyword_in_transcript(transcript, keyword, max_matches=1)
            if matches:
                match = matches[0]
                results.append({
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
                continue

        # No transcript or no match — still include the video (start from beginning)
        results.append({
            'video_id': video_id,
            'title': video['title'],
            'url': video['url'],
            'thumbnail': video['thumbnail'],
            'timestamp_start': 0,
            'timestamp_end': CLIP_DURATION,
            'transcript_snippet': '',
            'channel': video.get('channel', 'Unknown'),
            'source': 'youtube',
        })

    return results
