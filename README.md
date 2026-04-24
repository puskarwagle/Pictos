# NarrateImage

NarrateImage is a tool designed for video creators to streamline the process of finding visual assets for their scripts. It uses AI to analyze your script, breaks it into logical segments, extracts visual keywords, and automatically downloads relevant background images from Pinterest.

## Features

- **Script Management**: Easily browse and select Markdown scripts from your `video-scripts/` directory.
- **AI-Powered Analysis**: Leverages DeepSeek (via OpenAI-compatible API) to segment your script and generate highly relevant visual keywords.
- **Automated Pinterest Scraping**: Uses Playwright to search and download images from Pinterest based on AI-generated keywords.
- **Persistent Caching**: AI responses are saved locally in the `ai_responses/` directory (using the script's filename as a key), allowing you to reload previous analyses without re-calling the API.
- **Interactive Web Interface**: A clean, single-page application to edit scripts, trigger the AI analysis, and preview downloaded images.
- **Last Session Memory**: Remembers your last selected script across browser sessions.

## Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Frontend**: Vanilla JS, HTML5, CSS3
- **AI Integration**: OpenAI SDK (configured for DeepSeek)
- **Web Scraping**: Playwright (Chromium)
- **Environment Management**: python-dotenv

## Project Structure

```text
/
├── main.py                # FastAPI application & API endpoints
├── pinterest_scraper.py   # Pinterest scraping logic using Playwright
├── prompt.txt             # System prompt for AI keyword extraction
├── video-scripts/         # Store your Markdown (.md) scripts here
├── downloaded_images/     # Downloaded assets categorized by segment
├── ai_responses/          # Cached AI analysis results (JSON format)
├── static/                # Frontend assets (JS, CSS)
└── templates/             # HTML templates
```

## Setup Instructions

### 1. Clone the repository
```bash
git clone <repository-url>
cd narrateImage
```

### 2. Install Dependencies
```bash
pip install fastapi uvicorn openai playwright python-dotenv
playwright install chromium
```

### 3. Configuration
Create a `.env` file in the root directory and add your DeepSeek API credentials:
```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 4. Add Scripts
Place your video scripts in the `video-scripts/` folder as `.md` files. You can include hints in the script like `(1) [keyword1, keyword2]` to guide the AI.

## Usage

1. **Start the server**:
   ```bash
   python main.py
   ```
2. **Access the Web UI**:
   Open your browser and navigate to `http://localhost:8000`.
3. **Process a Script**:
   - Select a script from the sidebar.
   - Click **"Load Last Response"** to retrieve a previously saved AI analysis for that script.
   - Or click **"Process with AI"** to generate fresh segments and keywords.
   - Review/Edit the keywords if necessary.
   - Click **"Download Images"** to fetch matching visuals from Pinterest.

## Troubleshooting

- **404 Errors on Response**: Ensure that your script filenames do not contain multiple dots (e.g., use `part1.md` instead of `part.1.md`) as the system uses the file's stem for caching.
- **Pinterest Scraping**: If images aren't downloading, ensure Playwright is correctly installed and that you have a stable internet connection. Headless mode is enabled by default.

## License

MIT
