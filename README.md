# NarrateImage

NarrateImage is a specialized tool for video creators (AI creators, documentary filmmakers, etc.) to streamline the process of finding visual assets. It uses AI to analyze your scripts, breaks them into logical segments, and manages a persistent library of visual assets linked to your content.

## Core Features

- **Interactive Script Analysis**: Breaks your script into meaningful segments with AI-generated visual keywords.
- **Categorized Multi-Source Selection**: Choose from multiple image sources simultaneously using a categorized checkbox system:
    - **Scrapers**: **Pinterest** (diagrams/infographics) and **Unsplash** (photography).
    - **Photography APIs**: Lorem Picsum.
    - **Art & Museum**: NASA Images, Metropolitan Museum of Art.
    - **Avatars & Illustrations**: DiceBear, RoboHash, UI Avatars.
- **Merged AI Keywords**: When multiple scrapers are selected, the AI generates optimized keyword sets for each, merged in the UI for comprehensive results.
- **Robust Metadata Linking**: Uses a SQLite backend to anchor images to specific **text spans** (content-hashed) with advanced tracking for `last_used` and `user_touched` status.
- **Smart Fuzzy Matching**: Automatically re-anchors images to sentences even after text edits (92% similarity threshold).
- **Enhanced Image Pinning**: Lock 📌 images to a text anchor with optional **custom notes** to ensure they survive script re-segmentations.
- **Two-Step Deduplication**: Prevents duplicates via **source URL** checks (pre-download) and **SHA-256 binary hashing** (post-download).
- **Interactive Queue**: Fetch images by clicking keywords, managed by a concurrency queue (max 4 requests) with real-time speed (KB/s) and size metrics.
- **Batch Operations**: Quickly manage your library with "Delete Selected" bulk actions.
- **Persistent Resizable UI**: A modern, togglable Dark/Light mode interface with a **draggable sidebar** that remembers its dimensions and state via `localStorage`.
- **Reference-Counted Maintenance**: The Garbage Collector safely purges files only when zero active or pinned records reference them, following a default **30-day TTL**.

## Tech Stack

- **Backend**: FastAPI (Python 3.13)
- **Database**: SQLite3 (with advanced tracking columns)
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3 (BEM methodology)
- **Scraping**: [Camoufox](https://github.com/HMaker/camoufox) (Anti-detect browser for stealth scraping)
- **AI Integration**: OpenAI SDK (configured for **DeepSeek-V3**)
- **Environment**: python-dotenv for secure configuration

## File Guide

### Root Directory
- `main.py`: Entry point for the FastAPI application.
- `requirements.txt`: Project dependencies.
- `app/`:
    - `api/`: API routes (`routes.py`).
    - `core/`: Configuration and constants (`config.py`).
    - `db/`: Database session and repository logic (`session.py`, `repository.py`).
    - `models/`: Pydantic models (`api_models.py`).
    - `services/`: AI integration, image providers, and management services.
    - `static/` & `templates/`: Frontend UI assets and layout.
- `data/`: Local storage for scripts, images, and AI responses (Git ignored).
- `resources/prompts/`: AI system prompts for different visual styles.
- `scripts/`:
    - `garbage_collect.py`: Purge unused assets with TTL logic.
    - `migrate_to_db.py`: Utility to migrate legacy filesystem metadata to SQLite.
- `tests/`: Comprehensive test suite.

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file in the root:
```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
USE_DB_READ=true
```

### 3. Usage
1. Place a markdown script in `data/video_scripts/`.
2. Start the server: `python main.py`.
3. Open `http://localhost:8000`.
4. Select your script and choose **Image Sources** from the categorized checkboxes.
5. Click **"Process with AI"**.
6. **Maintenance**: Run `PYTHONPATH=. python scripts/garbage_collect.py --no-dry-run` to clean up old deleted assets (30-day TTL by default).
7. **Legacy Data**: Use `scripts/migrate_to_db.py` to import assets from older versions.

## Testing
The project includes a `pytest` suite.
```bash
# Run all tests
PYTHONPATH=. pytest
```

## Asset Persistence Model
Unlike folder-based systems, NarrateImage uses a **Content-to-Asset** mapping:
1. **Hash the Text**: Every segment's text is hashed (SHA-256) to create a stable "Anchor".
2. **Deduplicate the Asset**: 
    - **URL Check**: If the same URL is requested, the system reuses the existing record.
    - **Binary Hash**: Freshly downloaded images are hashed. If the bytes match an existing file, the new file is deleted and the DB record is linked to the existing one.
3. **Tracking & TTL**: 
    - `user_touched`: Any image interacted with by the user is protected from auto-deletion.
    - `last_used`: Tracks recency for smart cleanup.
4. **Fuzzy Recovery**: If you change "Hello world" to "Hello world!", the system sees high similarity and automatically re-anchors your images.
5. **Stable Storage**: Files are saved as `downloaded_images/{script_id}/{uuid}.jpg`. The DB handles a many-to-one relationship.
6. **Safe GC**: The Garbage Collector uses reference counting. It will only `unlink()` a file if no active or pinned database records point to it and it has exceeded the TTL.

## License
MIT
