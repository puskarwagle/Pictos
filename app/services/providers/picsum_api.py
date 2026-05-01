"""
Lorem Picsum — random curated photography.
https://picsum.photos
No API key needed.
"""

import httpx
import random


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Fetch random curated photos from Lorem Picsum.
    The query is unused since Picsum only serves random images,
    but we use it to vary the page for slight randomness.
    """
    page = random.randint(1, 50)
    url = f"https://picsum.photos/v2/list?page={page}&limit={count}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        items = resp.json()

    results = []
    for item in items:
        pic_id = item["id"]
        results.append({
            "url": f"https://picsum.photos/id/{pic_id}/800/600",
            "thumbnail": f"https://picsum.photos/id/{pic_id}/200/150",
            "title": f"Photo by {item.get('author', 'Unknown')}",
            "author": item.get("author"),
            "license": "Unsplash License",
            "source": "picsum",
        })

    return results
