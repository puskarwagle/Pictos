"""
UI Avatars — letter-based initials avatars.
https://ui-avatars.com/api
No API key needed. URLs are deterministic — no HTTP search call.
"""

import hashlib
from urllib.parse import quote

# Curated background colors for variety
BG_COLORS = ["0D8ABC", "E91E63", "9C27B0", "4CAF50", "FF9800", "607D8B", "795548"]


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Generate deterministic UI Avatars URLs from query text.
    Uses different background colors for variety.
    """
    results = []
    for i in range(count):
        # Vary the name slightly for each result
        name = f"{query} {i}" if i > 0 else query
        encoded_name = quote(name)
        bg = BG_COLORS[i % len(BG_COLORS)]
        results.append({
            "url": f"https://ui-avatars.com/api/?name={encoded_name}&background={bg}&color=fff&size=256&format=png&bold=true",
            "thumbnail": f"https://ui-avatars.com/api/?name={encoded_name}&background={bg}&color=fff&size=96&format=png&bold=true",
            "title": f"Avatar: {name}",
            "author": "UI Avatars",
            "license": "Free",
            "source": "uiavatars",
        })

    return results
