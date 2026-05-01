"""
RoboHash — deterministic robot/monster avatar generation.
https://robohash.org
No API key needed. URLs are deterministic — no HTTP search call.
"""

from urllib.parse import quote

# set1=robots, set2=monsters, set3=heads, set4=cats
SETS = ["set1", "set2", "set3", "set4"]


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Generate deterministic RoboHash avatar URLs from query seed.
    Each result uses a different set for variety.
    """
    results = []
    for i in range(count):
        robot_set = SETS[i % len(SETS)]
        seed = quote(f"{query}_{i}")
        results.append({
            "url": f"https://robohash.org/{seed}.png?size=300x300&set={robot_set}",
            "thumbnail": f"https://robohash.org/{seed}.png?size=100x100&set={robot_set}",
            "title": f"RoboHash ({robot_set}): {query}",
            "author": "RoboHash",
            "license": "CC BY 4.0",
            "source": "robohash",
        })

    return results
