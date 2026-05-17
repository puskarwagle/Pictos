"""
The Metropolitan Museum of Art Collection API — fine art, artifacts.
https://collectionapi.metmuseum.org/public/collection/v1
No API key needed. Two-step: search for IDs, then fetch object details.
"""

import asyncio
import httpx

BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
MAX_PARALLEL_FETCHES = 10


async def _fetch_object(client: httpx.AsyncClient, object_id: int) -> dict | None:
    """Fetch a single object's details. Returns None if no image available."""
    try:
        resp = await client.get(f"{BASE_URL}/objects/{object_id}")
        resp.raise_for_status()
        obj = resp.json()
    except Exception:
        return None

    primary = obj.get("primaryImage", "")
    if not primary:
        return None

    return {
        "url": primary,
        "thumbnail": obj.get("primaryImageSmall", primary),
        "title": obj.get("title", "Untitled"),
        "author": obj.get("artistDisplayName") or "Unknown Artist",
        "license": "Public Domain (CC0)",
        "source": "met_museum",
    }


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Search Met Museum collection. Two-step process:
    1. Search for object IDs matching query
    2. Fetch details for each ID (parallel, capped at MAX_PARALLEL_FETCHES)
    Skips objects with no primaryImage, fetches extras until count is met.
    """
    async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        # Step 1: Search for object IDs
        resp = await client.get(
            f"{BASE_URL}/search",
            params={"q": query, "hasImages": "true"},
        )
        resp.raise_for_status()
        data = resp.json()

    object_ids = data.get("objectIDs", []) or []
    if not object_ids:
        return []

    # Step 2: Fetch object details in batches until we have enough
    results = []
    offset = 0

    async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        while len(results) < count and offset < len(object_ids):
            batch_ids = object_ids[offset:offset + MAX_PARALLEL_FETCHES]
            offset += MAX_PARALLEL_FETCHES

            tasks = [_fetch_object(client, oid) for oid in batch_ids]
            batch_results = await asyncio.gather(*tasks)

            for obj in batch_results:
                if obj is not None:
                    results.append(obj)
                    if len(results) >= count:
                        break

    return results[:count]
