# NarrateImage

NarrateImage is a specialized tool for video creators (AI creators, documentary filmmakers, etc.) to streamline the process of finding visual assets. It uses AI to analyze your scripts, breaks them into logical segments, and manages a persistent library of visual assets linked to your content.

## Core Features

- **Interactive Script Analysis**: Breaks your script into meaningful segments with AI-generated visual keywords.
- **Multi-Source Scraping & APIs**: 
    - **Browser Scrapers**: Support for **Pinterest** (great for diagrams and infographics) and **Unsplash** (ideal for high-quality photography). Use both simultaneously for comprehensive asset gathering.
    - **Free Image APIs**: Direct integration with 6 free APIs for specialized generation without browsers:
        - **Photography**: Lorem Picsum
        - **Archival/Museum**: NASA Images, Metropolitan Museum of Art
        - **Avatars/Illustrations**: DiceBear, RoboHash, UI Avatars
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
- `main.py`: Entry point for the FastAPI application.
- `requirements.txt`: Project dependencies.
- `app/`:
    - `api/`: API routes (`routes.py`).
    - `core/`: Configuration and constants (`config.py`).
    - `db/`: Database session and repository logic (`session.py`, `repository.py`).
    - `models/`: Pydantic models.
    - `services/`: AI integration and image management services.
    - `static/` & `templates/`: Frontend UI assets.
- `data/`: Local storage for scripts, images, and AI responses (Git ignored).
- `resources/prompts/`: AI system prompts for different visual styles.
- `scripts/`: Maintenance utilities (`garbage_collect.py`, `migrate_to_db.py`).
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
4. Select your script and choose an **Image Source** from the dropdown menu.
5. Click **"Process with AI"**.
6. **Maintenance**: Run `PYTHONPATH=. python scripts/garbage_collect.py --no-dry-run` to clean up old deleted assets.

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
3. **Fuzzy Recovery**: If you change "Hello world" to "Hello world!", the system sees high similarity and automatically re-anchors your images.
4. **Stable Storage**: Files are saved as `downloaded_images/{script_id}/{uuid}.jpg`. The DB handles a many-to-one relationship.
5. **Safe GC**: The Garbage Collector uses reference counting. It will only `unlink()` a file if no active or pinned database records point to it.

## License
MIT
