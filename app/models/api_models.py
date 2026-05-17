from typing import List, Optional, Any
from pydantic import BaseModel

class ScriptSegment(BaseModel):
    id: int
    text: str
    keywords: List[str]
    images: Optional[List[Any]] = []

class ProcessRequest(BaseModel):
    filename: str
    script_text: str
    source: Optional[str] = "pinterest"

class DownloadRequest(BaseModel):
    filename: str
    segments: List[ScriptSegment]

class SaveSegmentsRequest(BaseModel):
    filename: str
    segments: List[ScriptSegment]

class KeywordDownloadRequest(BaseModel):
    filename: str
    segment_id: int
    keyword: str
    source: Optional[str] = "pinterest"

class DeleteImagesRequest(BaseModel):
    image_paths: List[str]

class ApiFetchRequest(BaseModel):
    filename: str
    segment_id: int
    keyword: str
    provider: str

class PinImageRequest(BaseModel):
    image_path: str
    pin: bool
    note: Optional[str] = None

class TranslateRequest(BaseModel):
    keyword: str
