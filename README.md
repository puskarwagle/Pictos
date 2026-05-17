# NarrateImage (AI YouTube Clip Finder)

NarrateImage is a specialized tool for video creators (AI creators, documentary filmmakers, YouTubers, etc.) to streamline the process of finding and managing visual assets. Instead of static images, it uses AI to analyze your narration scripts, breaks them into logical segments, and searches YouTube using `yt-dlp` and `youtube-transcript-api` to find and segment exact video clips matching your visual keywords based on spoken transcripts.

---

## 🏗 System Architecture & Data Flow

NarrateImage is built with a **Python (FastAPI)** backend and a **Vanilla JavaScript** frontend, using **SQLite3** for robust data persistence.

### High-Level Component Diagram
```text
[ Frontend (Vanilla JS) ] <--> [ API (FastAPI) ] <--> [ SQLite DB ]
          |                        |                      |
          |                        +--> [ AI Service (DeepSeek) ]
          |                        +--> [ YouTube & Transcript Services (yt-dlp) ]
          +--> [ Local Storage (Clips/Scripts) ]
```

### Core Data Flow
1.  **Ingestion:** The user places an `.md` script in `data/video_scripts/`.
2.  **Analysis:** The AI (`ai_service.py`) chunks the script, performs vibe analysis, and generates a **Dense Visual Mapping** (anchors + keywords).
3.  **Persistence:** 
    -   Script text is stored and hashed into **Text Anchors**.
    -   YouTube clips are matched and linked to these anchors in the `clips` SQLite table.
4.  **Retrieval:** The frontend (`ui.js`) renders segments. Clicking a keyword triggers the **Download Queue** (`queue.js`), which searches YouTube and matches transcripts via the backend.
5.  **Alignment:** The backend searches YouTube, aligns keyword occurrences with video transcripts, downloads thumbnails, and returns the exact video segment start/end timestamps.

---

## 🌟 Key Features

### 🧠 Intelligent Script Processing
-   **DeepSeek Integration:** Uses the OpenAI SDK to communicate with DeepSeek-V3 for high-density keyword extraction.
-   **Fuzzy Matching (92%):** When you edit your script in the editor, the system uses `difflib` to automatically re-anchor existing clips to the updated text segments, preventing data loss during script refinement.

### 🎥 Precise YouTube Clip Finder
-   **Transcript Alignment:** Searches YouTube and fetches transcripts automatically. Aligns the search phrase with English or auto-generated subtitles to center a 10-second clip on the exact moment the phrase is spoken.
-   **Local Thumbnail Caching:** Automatically downloads and caches YouTube thumbnails locally to ensure highly responsive, offline-capable grid rendering.
-   **Stable Pinning:** Pin 📌 clips to specific text anchors. Pins survive script re-segmentation and are protected from the garbage collector.

### ⚡️ Interactive Premium Frontend
-   **In-App Video Playback Modal:** Double-clicking any clip card launches a fluid, interactive video player modal containing a YouTube embed configured to start precisely at the matched transcript timestamp with autoplay enabled.
-   **Draggable Resizer Sidebar:** Seamlessly drag to expand the visual assets panel. Width preference is cached along with Dark/Light mode in the user's browser `localStorage`.
-   **Concurrency-Limited Queue:** Manages background YouTube queries and metadata retrieval with real-time speed and duration timing indicators.

---

## 📁 Directory Guide

### `app/` (The Application Core)
-   `api/routes.py`: The central hub for all HTTP endpoints.
-   `core/config.py`: System-wide settings and directory initialization.
-   `db/`:
    -   `session.py`: SQLite connection management (WAL mode enabled) and table schemas.
    -   `repository.py`: Low-level SQL queries and data access layer.
-   `services/`:
    -   `ai_service.py`: Script chunking, vibe analysis, and DeepSeek orchestration.
    -   `clip_service.py`: Logic for storing, retrieving, and downloading local clip thumbnails.
    -   `youtube_service.py`: Orchestrates yt-dlp search and youtube-transcript-api transcript alignment.
-   `static/`: The frontend layer (JS modules, CSS segments, assets).
-   `templates/`: HTML entry point.

### `data/` (The Persistence Layer - Git Ignored)
-   `video_scripts/`: Source `.md` scripts.
-   `ai_responses/`: Cached JSON results from the AI pipeline.
-   `downloaded_clips/`: Local thumbnail images organized by script ID.

### `resources/`
-   `prompts/`: Version-controlled AI instructions for different visual styles (archival, photography, etc.).
-   `providers_manifest.json`: Configuration for the active YouTube provider source.

---

## 🛠 Setup & Development

### 1. Prerequisites
-   Python 3.13+
-   A DeepSeek API Key

### 2. Installation
Ensure all system dependencies are installed and then install the Python packages:
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root:
```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
USE_DB_READ=true
CLIP_DURATION=10
```

### 4. Running the App
```bash
# Start the FastAPI server
python main.py
```
Visit `http://localhost:8000` to begin.

---

## 📜 License
MIT
