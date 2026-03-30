from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies.auth import get_current_active_user
from app.schemas.video import VideoMetadata, VideoResponse
from app.services.video_service import video_service


logger = logging.getLogger("cypath_lite.api.videos")

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    location_label: Optional[str] = Query(default=None),
    camera_type: Optional[str] = Query(default=None),
    captured_at: Optional[datetime] = Query(default=None),
    _user=Depends(get_current_active_user),
) -> Any:
    try:
        return video_service.upload_video(
            file=file,
            uploaded_by=_user.id,
            location_label=location_label,
            camera_type=camera_type,
            captured_at=captured_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from None


@router.get("", response_model=list[VideoResponse])
async def list_videos(_user=Depends(get_current_active_user)) -> Any:
    return video_service.list_videos(user_id=_user.id)


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int, _user=Depends(get_current_active_user)) -> Any:
    video = video_service.get_video(video_id=video_id, user_id=_user.id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.delete("/{video_id}", status_code=status.HTTP_200_OK)
async def delete_video(video_id: int, _user=Depends(get_current_active_user)) -> dict[str, str]:
    ok = video_service.delete_video(video_id=video_id, user_id=_user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return {"detail": "Video deleted"}


@router.get("/{video_id}/metadata", response_model=VideoMetadata)
async def get_video_metadata(video_id: int, _user=Depends(get_current_active_user)) -> Any:
    meta = video_service.get_video_metadata(video_id=video_id, user_id=_user.id)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return meta

