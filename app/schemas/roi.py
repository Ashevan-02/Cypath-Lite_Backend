from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float = Field(..., ge=0)
    y: float = Field(..., ge=0)


class ROIPolygonInput(BaseModel):
    # Polygon coordinates in pixel space: [[x1,y1],[x2,y2],...]
    polygon: List[Point] = Field(min_length=3)


class ROICreateInput(BaseModel):
    polygon: List[Point] = Field(min_length=3)


class ROIUpdateInput(BaseModel):
    polygon: List[Point] = Field(min_length=3)


class ROIResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    video_id: int
    polygon_json: list
    created_by: int


class ROIMetadataResponse(BaseModel):
    video_id: int
    rois: List[ROIResponse]

