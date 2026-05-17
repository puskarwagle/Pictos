# NarrateImage

NarrateImage is a specialized tool for video creators (AI creators, documentary filmmakers, etc.) to streamline the process of finding and managing visual assets. It uses AI to analyze your scripts, breaks them into logical segments, and manages a persistent, deduplicated library of visual assets linked directly to your text content.

---

## 🏗 System Architecture & Data Flow

NarrateImage is built with a **Python (FastAPI)** backend and a **Vanilla JavaScript** frontend, using **SQLite3** for robust data persistence.

### High-Level Component Diagram
```text
[ Frontend (Vanilla JS) ] <--> [ API (FastAPI) ] <--> [ SQLite DB ]
          |                        |                      |
          |                        +--> [ AI Service (DeepSeek) ]
          |                        +--> [ Provider Services (Scrapers/APIs) ]
          +--> [ Local Storage (Images/Scripts) ]
```

### Core Data Flow
1.  **Ingestion:** The user places an `.md` script in `data/video_scripts/`.
2.  **Analysis:** The AI (`ai_service.py`) chunks the script, performs vibe analysis, and generates a **Dense Visual Mapping** (anchors + keywords).
3.  **Persistence:** 
    -   Script text is stored and hashed into **Text Anchors**.
    -   Images are downloaded and linked to these anchors in the `images` table.
4.  **Retrieval:** The frontend (`ui.js`) renders segments. Clicking a keyword triggers the **Download Queue** (`queue.js`), which fetches assets via the backend.
5.  **Deduplication:** The backend (`image_service.py`) ensures no duplicate images exist on disk by checking both source URLs and binary SHA-256 hashes.

---

## 🌟 Key Features

### 🧠 Intelligent Script Processing
-   **DeepSeek Integration:** Uses the OpenAI SDK to communicate with DeepSeek-V3 for high-density keyword extraction.
-   **Fuzzy Matching (92%):** When you edit your script, the system uses `difflib` to automatically re-anchor existing images to the updated text segments, preventing data loss during refinement.

### 🖼 Advanced Asset Management
-   **Two-Step Deduplication:**
    -   **Pre-download:** Checks if the source URL already exists in the database.
    -   **Post-download:** Performs a binary SHA-256 hash on the file. If it matches an existing file, the new one is deleted and the DB record points to the original.
-   **Stable Pinning:** Pin 📌 images to specific text anchors. Pins survive script re-segmentation and are protected from the garbage collector.

### ⚡️ Interactive Frontend
-   **Concurrency-Limited Queue:** Manages background image downloads (max 4 parallel) with real-time speed (KB/s) and duration metrics.
-   **Dual-View Orchestration:** Seamlessly switch between **Edit Mode** (raw text) and **Segments Mode** (interactive keywords and images).
-   **Persistent UI State:** Remembers your Dark/Light mode preference and draggable sidebar width via `localStorage`.

### 🧹 Automated Maintenance
-   **Reference-Counted GC:** The `garbage_collect.py` script safely purges unused files only when zero active or pinned DB records reference them, following a configurable TTL.

---

## 📁 Directory Guide

### `app/` (The Application Core)
-   `api/routes.py`: The central hub for all HTTP endpoints.
-   `core/config.py`: System-wide settings and directory initialization.
-   `db/`:
    -   `session.py`: SQLite connection management (WAL mode enabled).
    -   `repository.py`: Low-level SQL queries and data access layer.
-   `services/`:
    -   `ai_service.py`: Script chunking, vibe analysis, and DeepSeek orchestration.
    -   `image_service.py`: The logic for downloading, hashing, and deduping images.
    -   `providers/`: Specialized scrapers (Pinterest/Unsplash) and API wrappers (NASA, Met, etc.).
-   `static/`: The frontend layer (JS modules, CSS segments, assets).
-   `templates/`: HTML entry point.

### `data/` (The Persistence Layer - Git Ignored)
-   `video_scripts/`: Source `.md` files.
-   `ai_responses/`: Cached JSON results from the AI pipeline.
-   `downloaded_images/`: Physical image storage, organized by script ID.

### `resources/`
-   `prompts/`: Version-controlled AI instructions for different visual styles (archival, photography, etc.).
-   `providers_manifest.json`: Configuration for available image sources.

---

## 🛠 Setup & Development

### 1. Prerequisites
-   Python 3.13+
-   A DeepSeek API Key

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root:
```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
USE_DB_READ=true
```

### 4. Running the App
```bash
# Start the FastAPI server
python main.py
```
Visit `http://localhost:8000` to begin.

### 5. Maintenance Commands
```bash
# Clean up orphaned/deleted assets (Dry run by default)
PYTHONPATH=. python scripts/garbage_collect.py

# Commit cleanup (Force delete)
PYTHONPATH=. python scripts/garbage_collect.py --no-dry-run
```

---

## 🧪 Testing
The project uses `pytest` for backend verification.
```bash
PYTHONPATH=. pytest
```

---

## 📜 License
MIT
