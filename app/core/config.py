import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Data directories
DATA_DIR = BASE_DIR / "data"
RESPONSES_DIR = DATA_DIR / "ai_responses"
DOWNLOAD_DIR = DATA_DIR / "downloaded_images"
SCRIPTS_DIR = DATA_DIR / "video_scripts"

# Resource directories
RESOURCES_DIR = BASE_DIR / "resources"
PROMPTS_DIR = RESOURCES_DIR / "prompts"

# Database
DB_PATH = BASE_DIR / "narrateimage.db"

# AI Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# Feature Flags
USE_DB_READ = os.getenv("USE_DB_READ", "False").lower() == "true"

# Ensure directories exist
for directory in [RESPONSES_DIR, DOWNLOAD_DIR, SCRIPTS_DIR, PROMPTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
