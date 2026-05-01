"""
DiceBear — deterministic avatar generation.
https://api.dicebear.com/7.x
No API key needed. URLs are deterministic — no HTTP search call.
"""

from urllib.parse import quote

STYLES = ["pixel-art", "avataaars", "bottts", "shapes", "thumbs"]


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Generate deterministic avatar URLs from query seed.
    Each result uses a different DiceBear style for variety.
    """
    results = []
    for i in range(count):
        style = STYLES[i % len(STYLES)]
        seed = quote(f"{query}_{i}")
        results.append({
            "url": f"https://api.dicebear.com/7.x/{style}/png?seed={seed}&size=256",
            "thumbnail": f"https://api.dicebear.com/7.x/{style}/png?seed={seed}&size=96",
            "title": f"{style} avatar: {query}",
            "author": "DiceBear",
            "license": "CC0",
            "source": "dicebear",
        })

    return results
