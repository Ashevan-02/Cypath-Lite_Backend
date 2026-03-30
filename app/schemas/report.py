from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


ReportType = Literal["PDF", "CSV"]


class ReportResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    run_id: int
    type: ReportType
    storage_path: str
    created_by: int
    created_at: datetime


class ReportListResponse(BaseModel):
    reports: list[ReportResponse]

