from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import get_current_active_user
from app.schemas.metrics import DetectionMetricsResponse, GroundTruthCreate, GroundTruthResponse
from app.services.metrics_service import metrics_service


logger = logging.getLogger("cypath_lite.api.metrics")

router = APIRouter(tags=["metrics"])


@router.post(
    "/runs/{run_id}/ground-truth",
    response_model=list[GroundTruthResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_ground_truth(
    run_id: int,
    entries: list[GroundTruthCreate],
    _user=Depends(get_current_active_user),
) -> Any:
    """
    Submit manually annotated ground truth violation frames for a run.
    Each entry is a frame_index + time_sec that is a known real violation.
    """
    if not entries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entries provided")
    try:
        return metrics_service.add_ground_truth(run_id=run_id, entries=entries, user_id=_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/runs/{run_id}/ground-truth", response_model=list[GroundTruthResponse])
async def list_ground_truth(run_id: int, _user=Depends(get_current_active_user)) -> Any:
    try:
        return metrics_service.list_ground_truth(run_id=run_id, user_id=_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/runs/{run_id}/metrics", response_model=DetectionMetricsResponse)
async def get_detection_metrics(run_id: int, _user=Depends(get_current_active_user)) -> Any:
    """
    Compute precision, recall, F1, and accuracy for a completed run
    against submitted ground truth annotations.
    """
    try:
        return metrics_service.compute_metrics(run_id=run_id, user_id=_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
