from typing import List, Optional, Any
from pydantic import BaseModel

class ScriptSegment(BaseModel):
    id: int
    text: str
    keywords: List[str]
    images: Optional[List[Any]] = []
    clips: Optional[List[Any]] = []

class ProcessRequest(BaseModel):
    filename: str
    script_text: str
    source: Optional[str] = "dense"

class DownloadRequest(BaseModel):
    filename: str
    segments: List[ScriptSegment]

class SaveSegmentsRequest(BaseModel):
    filename: str
    segments: List[ScriptSegment]

class ClipFetchRequest(BaseModel):
    filename: str
    segment_id: int
    keyword: str

class DeleteClipsRequest(BaseModel):
    clip_ids: List[str]

class PinClipRequest(BaseModel):
    clip_id: str
    pin: bool
    note: Optional[str] = None

class TranslateRequest(BaseModel):
    keyword: str
