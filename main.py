import uvicorn
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.db.session import init_db
from app.core.config import BASE_DIR, DOWNLOAD_DIR

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    yield
    # Shutdown logic (if any)

app = FastAPI(title="NarrateImage", lifespan=lifespan)

# Include API routes
app.include_router(router)

# Serve static files
# The paths are relative to BASE_DIR which is the project root
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app/static")), name="static")
app.mount("/data/downloaded_images", StaticFiles(directory=str(DOWNLOAD_DIR)), name="images")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
