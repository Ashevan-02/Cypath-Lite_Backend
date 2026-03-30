from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GroundTruthCreate(BaseModel):
    frame_index: int = Field(..., ge=0)
    time_sec: float = Field(..., ge=0.0)


class GroundTruthResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    run_id: int
    frame_index: int
    time_sec: float
    created_by: int
    created_at: datetime


class DetectionMetricsResponse(BaseModel):
    run_id: int
    total_ground_truth: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
