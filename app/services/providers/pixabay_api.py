"""
Pixabay API — photos, illustrations, and vector graphics.
https://pixabay.com/api/docs/
Requires PIXABAY_API_KEY.
"""

import httpx
from app.core.config import PIXABAY_API_KEY


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Search Pixabay for images matching query.
    """
    if not PIXABAY_API_KEY:
        return []

    url = "https://pixabay.com/api/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "per_page": max(3, count),  # Pixabay requires per_page >= 3
        "image_type": "all",  # Includes photos, illustrations, vectors
        "safesearch": "true"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    hits = data.get("hits", [])
    results = []

    for hit in hits:
        results.append({
            "url": hit.get("largeImageURL"),
            "thumbnail": hit.get("webformatURL"),
            "title": hit.get("tags", "Pixabay Image"),
            "author": hit.get("user"),
            "license": "Pixabay License",
            "source": "pixabay",
        })

    return results
