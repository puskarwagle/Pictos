"""
NASA Images API — space, planets, galaxies, scientific imagery.
https://images-api.nasa.gov
No API key needed.
"""

import httpx


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Search NASA Image and Video Library for images matching query.
    """
    url = "https://images-api.nasa.gov/search"
    params = {
        "q": query,
        "media_type": "image",
        "page_size": count,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("collection", {}).get("items", [])
    results = []

    for item in items:
        # Extract metadata
        item_data = item.get("data", [{}])[0]
        title = item_data.get("title", "NASA Image")
        author = item_data.get("secondary_creator") or item_data.get("center", "NASA")

        # Extract image URLs from links array
        links = item.get("links", [])
        if not links:
            continue

        # Find thumbnail (rel=preview) and full-size (rel=canonical, then alternate, then first)
        thumbnail = None
        full_url = None

        for link in links:
            rel = link.get("rel", "")
            href = link.get("href", "")
            if not href:
                continue
            if rel == "preview":
                thumbnail = href
            elif rel == "canonical":
                full_url = href
            elif rel == "alternate" and not full_url:
                full_url = href

        # Fallback: use first link href if nothing matched
        if not full_url and links:
            full_url = links[0].get("href", "")
        if not thumbnail:
            thumbnail = full_url

        if full_url:
            results.append({
                "url": full_url,
                "thumbnail": thumbnail or full_url,
                "title": title,
                "author": author,
                "license": "Public Domain (NASA)",
                "source": "nasa",
            })

    return results
