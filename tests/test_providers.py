import pytest
from providers import picsum_api, dicebear_api, robohash_api, uiavatars_api, nasa_api, met_api
from collections import namedtuple

# Mocking httpx.AsyncClient simply
class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")

class MockAsyncClientpicsum:
    def __init__(self, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass
    async def get(self, url, params=None):
        return MockResponse([
            {"id": "100", "author": "John Doe", "width": 2500, "height": 1656, "url": "https://unsplash.com/...", "download_url": "https://picsum.photos/..."}
        ])

class MockAsyncClientNASA:
    def __init__(self, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass
    async def get(self, url, params=None):
        return MockResponse({
            "collection": {
                "items": [
                    {
                        "data": [{"title": "Moon", "secondary_creator": "NASA JPL"}],
                        "links": [
                            {"rel": "preview", "href": "thumbnail.jpg"},
                            {"rel": "canonical", "href": "full.jpg"}
                        ]
                    }
                ]
            }
        })

class MockAsyncClientMet:
    def __init__(self, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, exc_type, exc_val, exc_tb): pass
    async def get(self, url, params=None):
        if url.endswith("/search"):
            return MockResponse({"objectIDs": [1, 2]})
        elif url.endswith("/1"):
            return MockResponse({
                "title": "Sun God", 
                "artistDisplayName": "Ancient", 
                "primaryImage": "sun1-full.jpg", 
                "primaryImageSmall": "sun1-thumb.jpg"
            })
        elif url.endswith("/2"):
            # Mock empty image
            return MockResponse({
                "title": "No Image", 
                "artistDisplayName": "Ancient", 
                "primaryImage": "", 
                "primaryImageSmall": ""
            })


@pytest.mark.asyncio
async def test_picsum_search(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClientpicsum)
    results = await picsum_api.search("anything", count=1)
    assert len(results) == 1
    assert "id/100/800" in results[0]["url"]
    assert results[0]["author"] == "John Doe"

@pytest.mark.asyncio
async def test_dicebear_search():
    results = await dicebear_api.search("bob", count=2)
    assert len(results) == 2
    assert "bob_0" in results[0]["url"]
    assert "bob_1" in results[1]["url"]

@pytest.mark.asyncio
async def test_robohash_search():
    results = await robohash_api.search("alice", count=2)
    assert len(results) == 2
    assert "set1" in results[0]["url"]
    assert "alice_0" in results[0]["url"]

@pytest.mark.asyncio
async def test_uiavatars_search():
    results = await uiavatars_api.search("charlie", count=1)
    assert len(results) == 1
    assert "charlie" in results[0]["url"]
    assert "ui-avatars" in results[0]["url"]

@pytest.mark.asyncio
async def test_nasa_search(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClientNASA)
    results = await nasa_api.search("moon", count=1)
    assert len(results) == 1
    assert results[0]["title"] == "Moon"
    assert results[0]["thumbnail"] == "thumbnail.jpg"
    assert results[0]["url"] == "full.jpg"
    assert results[0]["source"] == "nasa"

@pytest.mark.asyncio
async def test_met_search(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClientMet)
    results = await met_api.search("sun", count=2)
    assert len(results) == 1 # 2nd ID has no image, gets skipped
    assert results[0]["url"] == "sun1-full.jpg"
    assert results[0]["title"] == "Sun God"


# DB and Endpoint testing
def test_fetch_endpoint(client, test_db, monkeypatch):
    # Setup DB
    cursor = test_db.cursor()
    cursor.execute("INSERT INTO scripts (id, filename) VALUES (?, ?)", ("script_api", "test_api.md"))
    cursor.execute("INSERT INTO text_anchors (id, script_id, content, content_hash) VALUES (?, ?, ?, ?)",
                   ("anchor_api", "script_api", "Some text", "hash_api"))
    cursor.execute("INSERT INTO segments (id, script_id, anchor_id, ai_index, keywords) VALUES (?, ?, ?, ?, ?)",
                   ("seg_api", "script_api", "anchor_api", 1, '["key"]'))
    test_db.commit()

    import providers
    async def mock_search(query, count):
        return [{
            "url": "http://example.com/fake.png",
            "thumbnail": "http://example.com/fake.png",
            "title": "Fake",
            "author": "Mock",
            "license": "CC0",
            "source": "mock_provider"
        }]
    
    monkeypatch.setitem(providers.PROVIDERS, "mock_provider", mock_search)

    # Need to mock httpx get for the download step
    class MockHttpResp:
        def __init__(self):
            self.content = b"fake image bytes"
        def raise_for_status(self): pass

    class MockClientDownload:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url): return MockHttpResp()
    
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: MockClientDownload())

    payload = {
        "filename": "test_api.md",
        "segment_id": 1,
        "keyword": "key",
        "provider": "mock_provider"
    }

    response = client.post("/api/fetch", json=payload)
    if response.status_code != 200:
        print(response.json())
        
    assert response.status_code == 200
    data = response.json()
    assert len(data["images"]) == 1
    assert data["images"][0]["source"] == "mock_provider"

    # Verify DB
    cursor.execute("SELECT provider, api_type FROM images WHERE source = 'mock_provider'")
    row = cursor.fetchone()
    assert row["provider"] == "mock_provider"
    assert row["api_type"] == "api"

