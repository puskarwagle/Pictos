import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from pinterest_scraper import get_pinterest_images, download_images
from pathlib import Path

load_dotenv()

app = FastAPI()

# Configure DeepSeek client
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
)

# Ensure directories exist
DOWNLOAD_DIR = Path("downloaded_images")
SCRIPTS_DIR = Path("video-scripts")
RESPONSES_DIR = Path("ai_responses")
DOWNLOAD_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)
RESPONSES_DIR.mkdir(exist_ok=True)

class ScriptSegment(BaseModel):
    id: int
    text: str
    keywords: List[str]
    images: Optional[List[str]] = []

class ProcessRequest(BaseModel):
    filename: str
    script_text: str

class DownloadRequest(BaseModel):
    filename: str
    segments: List[ScriptSegment]

def attach_images_to_segments(segments: List[dict], filename: str):
    script_stem = Path(filename).stem
    for segment in segments:
        images = []
        if "keywords" in segment:
            # Strictly use the structured hierarchy: downloaded_images/script_name/segment_no/*/
            segment_base_dir = DOWNLOAD_DIR / script_stem / str(segment["id"])
            if segment_base_dir.exists():
                for kw_dir in segment_base_dir.iterdir():
                    if kw_dir.is_dir():
                        images.extend([f.as_posix() for f in kw_dir.glob("*.jpg")])
        
        segment["images"] = images
    return segments

@app.get("/api/scripts")
async def list_scripts():
    scripts = [f.name for f in SCRIPTS_DIR.glob("*.md")]
    return scripts

@app.get("/api/script/{filename}")
async def get_script(filename: str):
    script_path = SCRIPTS_DIR / filename
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    with open(script_path, "r") as f:
        return {"content": f.read()}

@app.get("/api/script/{filename}/response")
async def get_script_response(filename: str):
    # Use stem to avoid "part1.md.json"
    stem = Path(filename).stem
    response_file = RESPONSES_DIR / f"{stem}.json"
    if not response_file.exists():
        raise HTTPException(status_code=404, detail=f"No cached response found at {response_file}")
    with open(response_file, "r") as f:
        data = json.load(f)
        segments = data.get("segments", data) if isinstance(data, dict) else data
        return attach_images_to_segments(segments, filename)

@app.post("/api/process-script")
async def process_script(request: ProcessRequest):
    with open("prompt.txt", "r") as f:
        prompt_template = f.read()
    
    prompt = prompt_template.format(script_text=request.script_text)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts visual keywords from scripts. Output strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        result = json.loads(raw_content)
        
        # Save the AI response to a file
        stem = Path(request.filename).stem
        response_file = RESPONSES_DIR / f"{stem}.json"
        print(f"Saving response to {response_file}")
        with open(response_file, "w") as f:
            json.dump(result, f, indent=4)

        segments = result.get("segments", result) if isinstance(result, dict) else result
        return attach_images_to_segments(segments, request.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class KeywordDownloadRequest(BaseModel):
    filename: str
    segment_id: int
    keyword: str

@app.post("/api/download-keyword-images")
async def download_keyword_images(request: KeywordDownloadRequest):
    script_stem = Path(request.filename).stem
    # Hierarchy: script_name/segment_no/keyword_title/
    subfolder_name = f"{script_stem}/{request.segment_id}/{request.keyword.replace(' ', '_')}"
    
    try:
        loop = asyncio.get_event_loop()
        img_urls = await loop.run_in_executor(
            None, 
            get_pinterest_images, 
            request.keyword, 
            3, # number of images
            True # headless
        )
        
        if img_urls:
            await loop.run_in_executor(
                None,
                download_images,
                img_urls,
                subfolder_name
            )
            
            # Get the local paths of downloaded images
            segment_dir = DOWNLOAD_DIR / subfolder_name
            image_files = [f.as_posix() for f in segment_dir.glob("*.jpg")]
            return {"images": image_files}
        return {"images": []}
    except Exception as e:
        print(f"Error scraping for keyword {request.keyword}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download-images")
async def download_script_images(request: DownloadRequest):
    results = []
    script_stem = Path(request.filename).stem
    
    for segment in request.segments:
        segment_id = segment.id
        # Use the first keyword for searching
        if not segment.keywords:
            results.append(segment)
            continue
            
        primary_keyword = segment.keywords[0]
        # New hierarchy: script_name/segment_no/keyword_title/
        subfolder_name = f"{script_stem}/{segment_id}/{primary_keyword.replace(' ', '_')}"
        
        # Run scraping in a thread to avoid blocking
        try:
            loop = asyncio.get_event_loop()
            img_urls = await loop.run_in_executor(
                None, 
                get_pinterest_images, 
                primary_keyword, 
                3, # number of images per segment
                True # headless
            )
            
            if img_urls:
                await loop.run_in_executor(
                    None,
                    download_images,
                    img_urls,
                    subfolder_name
                )
                
                # Get the local paths of downloaded images
                segment_dir = DOWNLOAD_DIR / subfolder_name
                image_files = [f.as_posix() for f in segment_dir.glob("*.jpg")]
                segment.images = image_files
        except Exception as e:
            print(f"Error scraping for segment {segment_id}: {e}")
            
        results.append(segment)
        
    return results


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/downloaded_images", StaticFiles(directory="downloaded_images"), name="images")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("templates/index.html", "r") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
