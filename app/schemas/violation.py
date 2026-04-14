from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceInfo(BaseModel):
    evidence_path: Optional[str] = None


class ViolationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    run_id: int
    time_sec: float
    frame_index: int
    vehicle_class: str
    confidence: float
    bounding_box: Optional[list] = None
    evidence_path: Optional[str] = None
    is_false_positive: bool = False
    verified: bool = False
    created_at: datetime


class ViolationAnalyticsResponse(BaseModel):
    total_violations: int
    violations_by_vehicle_type: dict[str, int]
    violations_by_time_window: dict[str, int]
    hotspot_statistics: dict[str, int]

