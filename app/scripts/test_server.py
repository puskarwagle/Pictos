import httpx
import asyncio

async def test_static():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # We can't actually run the server, but we can check the FastAPI app object if we can import it
        pass

if __name__ == "__main__":
    # I can't run the server, so I'll just check the code again.
    pass
