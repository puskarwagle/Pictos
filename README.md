# NarrateImage

NarrateImage is a specialized tool for video creators (AI creators, documentary filmmakers, etc.) to streamline the process of finding visual assets. It uses AI to analyze your scripts, breaks them into logical segments, and allows you to interactively download relevant background images from Pinterest.

## Core Features

- **Interactive Script Analysis**: Breaks your script into meaningful segments with AI-generated visual keywords.
- **Smart Keyword Downloads**: Instead of bulk downloading, you can click individual keywords to fetch images. This allows for precise control over your visual assets.
- **Structured Asset Management**: Automatically organizes downloads into a clean hierarchy: `downloaded_images/{script_name}/{segment_id}/{keyword}/`.
- **Dynamic Local Sync**: On loading a script, the tool dynamically scans your local folders. If you manually add or delete images, the UI updates automatically.
- **Concurrency Control**: Features a built-in download queue that manages multiple parallel requests (max 4) to ensure stability and speed.
- **Dark/Light Mode**: A modern, togglable UI for comfortable use at any time of day.
- **Edit Mode**: Directly edit AI-generated text and keywords within the app to fine-tune your search.

## Tech Stack

- **Backend**: FastAPI (Python 3.13)
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3
- **Scraping**: [Camoufox](https://github.com/HMaker/camoufox) (A specialized browser for anti-detect scraping)
- **AI Integration**: OpenAI SDK (configured for DeepSeek-V3)
- **Environment**: python-dotenv for secure configuration

## File Guide

### Root Directory
- `main.py`: The heart of the application. It manages the FastAPI server, handles script processing, and performs dynamic scanning of the image directories.
- `pinterest_scraper.py`: Contains the logic for searching Pinterest and downloading images using Camoufox and Python's `ThreadPoolExecutor`.
- `prompt.txt`: The system prompt used to instruct the AI on how to segment the script and extract high-quality visual keywords.
- `migrate_images.py`: (Optional Utility) Used to migrate legacy flat folder structures to the new nested hierarchy.

### Directories
- `video-scripts/`: Place your `.md` script files here.
- `downloaded_images/`: Structured storage for all downloaded assets.
- `ai_responses/`: Local JSON cache of AI analyses. This allows you to "Load Last Response" without spending API tokens.
- `static/`:
    - `script.js`: Handles all UI logic, the download concurrency queue, and interactive rendering.
    - `style.css`: Modern styling with CSS variables for theme support and segment color-coding.
- `templates/`:
    - `index.html`: The main single-page application layout.

## Setup Instructions

### 1. Install Dependencies
Ensure you have Python 3.10+ installed.
```bash
pip install fastapi uvicorn openai camoufox python-dotenv
```

### 2. Configuration
Create a `.env` file in the root:
```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 3. Usage
1. Place a markdown script in `video-scripts/`.
2. Start the server: `python main.py`.
3. Open `http://localhost:8000` in your browser.
4. Select your script from the left sidebar.
5. Click **"Process with AI"** or **"Load Last Response"**.
6. **Click on individual keywords (tags)** to download images for that specific concept.

## How the Image Hierarchy Works
The system strictly enforces the following structure:
```text
downloaded_images/
└── {script_name}/
    └── {segment_id}/
        └── {keyword_with_underscores}/
            ├── image1.jpg
            ├── image2.jpg
            └── ...
```
This structure makes it easy to import your assets directly into video editors like Premiere Pro or CapCut.

## License
MIT
