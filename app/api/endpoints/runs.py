from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.auth import get_current_active_user
from app.schemas.run import RunCreateInput, RunResponse, RunStatusResponse, RunStatus
from app.services.detection_service import detection_service
from app.workers.tasks import process_video_analysis


logger = logging.getLogger("cypath_lite.api.runs")

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(payload: RunCreateInput, _user=Depends(get_current_active_user)) -> Any:
    try:
        run = detection_service.create_analysis_run(payload=payload, created_by=_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Enqueue async processing. If broker isn't reachable, keep the run QUEUED for later.
    try:
        process_video_analysis.delay(run.id)
    except Exception:
        logger.warning("Could not enqueue Celery analysis task; run remains QUEUED.", exc_info=True)

    return run


@router.get("", response_model=list[RunResponse])
async def list_runs(
    status: Optional[RunStatus] = Query(default=None),
    video_id: Optional[int] = Query(default=None),
    _user=Depends(get_current_active_user),
) -> Any:
    return detection_service.list_runs(status=status, video_id=video_id, user_id=_user.id)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, _user=Depends(get_current_active_user)) -> Any:
    run = detection_service.get_run(run_id=run_id, user_id=_user.id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: int, _user=Depends(get_current_active_user)) -> Any:
    run = detection_service.get_run(run_id=run_id, user_id=_user.id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(run_id: int, _user=Depends(get_current_active_user)) -> Any:
    run = detection_service.cancel_run(run_id=run_id, user_id=_user.id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run

