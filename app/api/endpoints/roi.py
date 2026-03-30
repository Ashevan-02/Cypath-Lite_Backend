from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.auth import get_current_active_user
from app.schemas.roi import ROICreateInput, ROIResponse, ROIUpdateInput, ROIMetadataResponse
from app.services.roi_service import roi_service


logger = logging.getLogger("cypath_lite.api.roi")

router = APIRouter(tags=["roi"])


@router.post("/videos/{video_id}/roi", response_model=ROIResponse, status_code=status.HTTP_201_CREATED)
async def create_roi(video_id: int, payload: ROICreateInput, _user=Depends(get_current_active_user)) -> ROIResponse:
    try:
        return roi_service.create_roi(video_id=video_id, payload=payload, created_by=_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/videos/{video_id}/roi", response_model=ROIMetadataResponse)
async def list_rois(video_id: int, _user=Depends(get_current_active_user)) -> ROIMetadataResponse:
    rois = roi_service.list_rois(video_id=video_id, user_id=_user.id)
    return {"video_id": video_id, "rois": rois}


@router.get("/roi/{roi_id}", response_model=ROIResponse)
async def get_roi(roi_id: int, _user=Depends(get_current_active_user)) -> ROIResponse:
    roi = roi_service.get_roi(roi_id=roi_id, user_id=_user.id)
    if not roi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ROI not found")
    return roi


@router.put("/roi/{roi_id}", response_model=ROIResponse)
async def update_roi(roi_id: int, payload: ROIUpdateInput, _user=Depends(get_current_active_user)) -> ROIResponse:
    roi = roi_service.update_roi(roi_id=roi_id, payload=payload, user_id=_user.id)
    if not roi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ROI not found")
    return roi


@router.delete("/roi/{roi_id}", status_code=status.HTTP_200_OK)
async def delete_roi(roi_id: int, _user=Depends(get_current_active_user)) -> dict[str, str]:
    ok = roi_service.delete_roi(roi_id=roi_id, user_id=_user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ROI not found")
    return {"detail": "ROI deleted"}

