from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import get_current_active_user
from app.schemas.violation import ViolationAnalyticsResponse, ViolationResponse
from app.services.analytics_service import analytics_service
from app.services.violation_service import violation_service


logger = logging.getLogger("cypath_lite.api.violations")

router = APIRouter(tags=["violations"])


@router.get("/runs/{run_id}/violations", response_model=list[ViolationResponse])
async def list_violations(run_id: int, _user=Depends(get_current_active_user)) -> Any:
    return violation_service.list_violations(run_id=run_id, user_id=_user.id)


@router.get("/violations/{violation_id}", response_model=ViolationResponse)
async def get_violation(violation_id: int, _user=Depends(get_current_active_user)) -> Any:
    violation = violation_service.get_violation(violation_id=violation_id, user_id=_user.id)
    if not violation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")
    return violation


@router.post("/violations/{violation_id}/flag-false-positive", response_model=ViolationResponse)
async def flag_false_positive(violation_id: int, _user=Depends(get_current_active_user)) -> Any:
    v = violation_service.flag_false_positive(violation_id=violation_id, user_id=_user.id)
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")
    return v


@router.post("/violations/{violation_id}/verify", response_model=ViolationResponse)
async def verify_violation(violation_id: int, _user=Depends(get_current_active_user)) -> Any:
    v = violation_service.verify_violation(violation_id=violation_id, user_id=_user.id)
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")
    return v


@router.get("/runs/{run_id}/analytics", response_model=ViolationAnalyticsResponse)
async def get_run_analytics(run_id: int, _user=Depends(get_current_active_user)) -> Any:
    return analytics_service.get_run_analytics(run_id=run_id, user_id=_user.id)

