from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    duration_seconds: Optional[float] = None
    resolution: Optional[str] = None
    file_size: Optional[int] = None
    captured_at: Optional[datetime] = None
    location_label: Optional[str] = None
    camera_type: Optional[str] = None


class VideoResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    filename: str
    storage_path: str
    media_type: str = "video"
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    resolution: Optional[str] = None
    location_label: Optional[str] = None
    camera_type: Optional[str] = None
    captured_at: Optional[datetime] = None
    uploaded_by: int
    created_at: datetime


class VideoCreateResponse(BaseModel):
    id: int
    filename: str
    storage_path: str
    metadata: VideoMetadata = Field(default_factory=VideoMetadata)

