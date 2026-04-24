# NarrateImage

NarrateImage is a specialized tool for video creators (AI creators, documentary filmmakers, etc.) to streamline the process of finding visual assets. It uses AI to analyze your scripts, breaks them into logical segments, and manages a persistent library of visual assets linked to your content.

## Core Features

- **Interactive Script Analysis**: Breaks your script into meaningful segments with AI-generated visual keywords.
- **Multi-Source Scraping**: Support for **Pinterest** (great for diagrams and infographics) and **Unsplash** (ideal for high-quality photography). Use both simultaneously for comprehensive asset gathering.
- **Robust Metadata Linking**: Uses a SQLite backend to anchor images to specific **text spans** (content-hashed) rather than unstable segment indices.
- **Smart Fuzzy Matching**: If you edit your script, the system uses fuzzy string matching (92% threshold) to ensure images stay linked to their original sentences.
- **Image Pinning**: Explicitly "lock" 📌 images to a text anchor so they survive even major script re-segmentations.
- **Two-Step Deduplication**: Prevents duplicate assets by checking both **source URLs** (pre-download) and **image binary hashes** (post-download SHA-256).
- **Interactive Keyword Downloads**: Click individual keywords to fetch images. Managed by a built-in concurrency queue (max 4 requests).
- **Soft Deletion & Reference-Counted Maintenance**: Deleting an image hides it from the UI. The Garbage Collector only permanently purges a physical file when **zero active or pinned records** reference it, safely handling shared assets.
- **Edit Mode**: Directly edit AI-generated text and keywords within the app.
- **Dark/Light Mode**: A modern, togglable UI for comfortable use.

## Tech Stack

- **Backend**: FastAPI (Python 3.13)
- **Database**: SQLite3
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3
- **Scraping**: [Camoufox](https://github.com/HMaker/camoufox) (A specialized browser for anti-detect scraping)
- **AI Integration**: OpenAI SDK (configured for DeepSeek-V3)
- **Environment**: python-dotenv for secure configuration

## File Guide

### Root Directory
- `main.py`: The heart of the application. Manages FastAPI routes, anchor matching logic, and DB integrations.
- `db.py`: Database schema and initialization logic.
- `migrate_to_db.py`: Utility to migrate existing legacy folders and AI responses into the metadata store.
- `garbage_collect.py`: Maintenance utility to purge orphaned or deleted images older than a set TTL (default 30 days).
- `pinterest_scraper.py`: Scrapes Pinterest using Camoufox.
- `unsplash_scraper.py`: Scrapes Unsplash photography using Camoufox.
- `prompt_pinterest.txt`: Optimized prompt for generating diagram/infographic keywords.
- `prompt_unsplash.txt`: Optimized prompt for generating photography-focused keywords.

### Directories
- `video-scripts/`: Place your `.md` script files here.
- `downloaded_images/`: Managed storage. Files are named with UUIDs and organized by script ID.
- `ai_responses/`: Legacy JSON cache of AI analyses (maintained as backup).
- `tests/`: Comprehensive test suite for backend and database logic.
- `static/`:
    - `script.js`: UI logic, pinning interactions, and download queue management.
    - `style.css`: Modern styling with CSS variables.

## Setup Instructions

### 1. Install Dependencies
```bash
pip install fastapi uvicorn openai camoufox python-dotenv pytest httpx
```

### 2. Configuration
Create a `.env` file in the root:
```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
USE_DB_READ=true
```

### 3. Usage
1. Place a markdown script in `video-scripts/`.
2. Start the server: `python main.py`.
3. Open `http://localhost:8000`.
4. Select your script and choose an **Image Source** (Pinterest, Unsplash, or Both).
5. Click **"Process with AI"**.
6. **Pin Images**: Click the 📌 icon on an image to lock it to that sentence.
7. **Maintenance**: Run `python garbage_collect.py --no-dry-run` to clean up old deleted assets.

## Testing
The project includes a `pytest` suite to ensure database integrity and route correctness.
```bash
# Run all tests
pytest

# Run with output
pytest -v
```

## Asset Persistence Model
Unlike folder-based systems, NarrateImage uses a **Content-to-Asset** mapping:
1. **Hash the Text**: Every segment's text is hashed (SHA-256) to create a stable "Anchor".
2. **Deduplicate the Asset**: 
    - **URL Check**: If the same URL is requested, the system reuses the existing record.
    - **Binary Hash**: Freshly downloaded images are hashed. If the bytes match an existing file, the new file is deleted and the DB record is linked to the existing one.
3. **Fuzzy Recovery**: If you change "Hello world" to "Hello world!", the system sees high similarity and automatically re-anchors your images.
4. **Stable Storage**: Files are saved as `downloaded_images/{script_id}/{uuid}.jpg`. The DB handles a many-to-one relationship.
5. **Safe GC**: The Garbage Collector uses reference counting. It will only `unlink()` a file if no active or pinned database records point to it.

## License
MIT
