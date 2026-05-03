"""
Pexels API — high-quality, cinematic photography and b-roll.
https://www.pexels.com/api/documentation/
Requires PEXELS_API_KEY.
"""

import httpx
from app.core.config import PEXELS_API_KEY


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Search Pexels for images matching query.
    """
    if not PEXELS_API_KEY:
        return []

    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": count,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    photos = data.get("photos", [])
    results = []

    for photo in photos:
        results.append({
            "url": photo.get("src", {}).get("original"),
            "thumbnail": photo.get("src", {}).get("large") or photo.get("src", {}).get("medium"),
            "title": f"Photo by {photo.get('photographer')}",
            "author": photo.get("photographer"),
            "license": "Pexels License",
            "source": "pexels",
        })

    return results
