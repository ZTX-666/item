from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Photo(BaseModel):
    id: str
    name: str
    url: str
    preview: str
    size: int
    type: str
    lastModified: int


class PhotoClassification(BaseModel):
    photo_id: str
    description: str
    category: str  # ex: "fundação", "estrutura", "acabamento", etc
    tags: List[str]
    confidence: float


class Audio(BaseModel):
    id: str
    name: str
    url: str
    duration: float
    size: int
    type: str


class AudioTranscription(BaseModel):
    audio_id: str
    transcription: str


class GenerateDiarioRequest(BaseModel):
    project_name: str
    project_location: str
    contractor: Optional[str] = None
    supervisor: Optional[str] = None
    photos: List[PhotoClassification]
    audio_transcription: Optional[str] = None


class PhotoOrderRequest(BaseModel):
    photo_ids: List[str]


class UploadResponse(BaseModel):
    success: bool
    message: str
    photo_id: Optional[str] = None
    audio_id: Optional[str] = None


class DiarioResponse(BaseModel):
    success: bool
    message: str
    download_url: Optional[str] = None
