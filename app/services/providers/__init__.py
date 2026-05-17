"""
Provider registry.
Maps provider names to their async search() functions.
"""

from app.services.youtube_service import search_and_match

PROVIDERS = {
    "youtube": search_and_match,
}

API_PROVIDERS = set(PROVIDERS.keys())
