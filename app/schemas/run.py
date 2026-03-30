from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


IntrusionMethod = Literal["BOTTOM_CENTER", "OVERLAP"]
RunStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]


class RunCreateInput(BaseModel):
    video_id: int
    roi_id: int
    sample_fps: int = Field(default=5, ge=1, le=60)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    persistence_frames: int = Field(default=3, ge=1, le=60)
    intrusion_method: IntrusionMethod = Field(default="BOTTOM_CENTER")
    overlap_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    resize_width: Optional[int] = Field(default=None, ge=64, le=4096)
    resize_height: Optional[int] = Field(default=None, ge=64, le=4096)

    @model_validator(mode="after")
    def validate_resize_pair(self) -> "RunCreateInput":
        if (self.resize_width is None) != (self.resize_height is None):
            raise ValueError("resize_width and resize_height must be provided together")
        return self


class RunResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    video_id: int
    roi_id: int
    status: RunStatus
    model_name: str
    sample_fps: int
    confidence_threshold: float
    persistence_frames: int
    resize_width: Optional[int]
    resize_height: Optional[int]
    intrusion_method: IntrusionMethod
    overlap_threshold: Optional[float]
    total_frames: int
    processed_frames: int
    total_violations: int
    progress_percentage: float
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    created_by: int
    created_at: datetime


class RunStatusResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    status: RunStatus
    progress_percentage: float
    processed_frames: int
    total_frames: int
    total_violations: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str] = None

