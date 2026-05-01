"""
Image provider registry.
Maps provider names to their async search() functions.
"""

from . import picsum_api, dicebear_api, robohash_api, uiavatars_api, nasa_api, met_api

PROVIDERS = {
    "picsum": picsum_api.search,
    "dicebear": dicebear_api.search,
    "robohash": robohash_api.search,
    "uiavatars": uiavatars_api.search,
    "nasa": nasa_api.search,
    "met": met_api.search,
}

# Set of provider names that use HTTP APIs (not Camoufox scrapers)
API_PROVIDERS = set(PROVIDERS.keys())
