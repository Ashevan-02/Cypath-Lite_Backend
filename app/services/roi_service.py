from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple

from app.core.database import SessionLocal
from app.models.roi import ROI
from app.models.video import Video
from app.schemas.roi import ROICreateInput, ROIUpdateInput
from app.services.audit_service import audit_service
from app.utils.frame_extractor import get_video_metadata


logger = logging.getLogger("cypath_lite.services.roi_service")


def _parse_resolution(resolution: str | None) -> Tuple[int, int] | None:
    if not resolution:
        return None
    # Expected: "WIDTHxHEIGHT"
    try:
        w_str, h_str = resolution.lower().split("x", 1)
        return int(float(w_str)), int(float(h_str))
    except Exception:
        return None


def _validate_polygon_in_frame(*, polygon: list[dict[str, float] | list[float]], frame_w: int, frame_h: int) -> None:
    pts: list[tuple[float, float]] = []
    for p in polygon:
        if isinstance(p, dict):
            x = float(p["x"])
            y = float(p["y"])
        else:
            x, y = float(p[0]), float(p[1])
        if x < 0 or y < 0 or x > frame_w or y > frame_h:
            raise ValueError("ROI points must be within frame dimensions")
        pts.append((x, y))
    if len(pts) < 3:
        raise ValueError("ROI polygon must have at least 3 points")


class ROIServices:
    def create_roi(self, *, video_id: int, payload: ROICreateInput, created_by: int) -> ROI:
        with SessionLocal() as db:
            video = db.query(Video).filter(Video.id == video_id, Video.uploaded_by == created_by).first()
            if not video:
                raise ValueError("Video not found or not owned by user")

            frame_dims = _parse_resolution(video.resolution)
            if not frame_dims:
                meta = get_video_metadata(video.storage_path)
                video.resolution = meta.get("resolution")  # type: ignore[assignment]
                db.commit()
                frame_dims = _parse_resolution(video.resolution)
            polygon_list = [[p.x, p.y] for p in payload.polygon]
            if frame_dims:
                _validate_polygon_in_frame(polygon=polygon_list, frame_w=frame_dims[0], frame_h=frame_dims[1])
            else:
                # If dimensions are unknown, still validate min points and numeric coords.
                if len(polygon_list) < 3:
                    raise ValueError("ROI polygon must have at least 3 points")

            roi = ROI(video_id=video_id, polygon_json=polygon_list, created_by=created_by)
            db.add(roi)
            db.commit()
            db.refresh(roi)
        audit_service.log(user_id=created_by, action="ROI_CREATE", entity_type="roi", entity_id=str(roi.id))
        return roi

    def list_rois(self, *, video_id: int, user_id: int) -> list[ROI]:
        with SessionLocal() as db:
            _ = db.query(Video).filter(Video.id == video_id, Video.uploaded_by == user_id).first()
            if not _:
                return []
            return db.query(ROI).filter(ROI.video_id == video_id).order_by(ROI.created_at.desc()).all()

    def get_roi(self, *, roi_id: int, user_id: int) -> Optional[ROI]:
        with SessionLocal() as db:
            roi = (
                db.query(ROI)
                .join(Video, Video.id == ROI.video_id)
                .filter(ROI.id == roi_id, Video.uploaded_by == user_id)
                .first()
            )
            return roi

    def update_roi(self, *, roi_id: int, payload: ROIUpdateInput, user_id: int) -> Optional[ROI]:
        with SessionLocal() as db:
            roi = (
                db.query(ROI)
                .join(Video, Video.id == ROI.video_id)
                .filter(ROI.id == roi_id, Video.uploaded_by == user_id)
                .first()
            )
            if not roi:
                return None

            video = db.query(Video).filter(Video.id == roi.video_id, Video.uploaded_by == user_id).first()
            frame_dims = _parse_resolution(video.resolution) if video else None
            if video and not frame_dims:
                meta = get_video_metadata(video.storage_path)
                video.resolution = meta.get("resolution")  # type: ignore[assignment]
                db.commit()
                frame_dims = _parse_resolution(video.resolution)
            polygon_list = [[p.x, p.y] for p in payload.polygon]
            if frame_dims:
                _validate_polygon_in_frame(polygon=polygon_list, frame_w=frame_dims[0], frame_h=frame_dims[1])

            roi.polygon_json = polygon_list
            roi.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(roi)
        if roi is not None:
            audit_service.log(user_id=user_id, action="ROI_UPDATE", entity_type="roi", entity_id=str(roi.id))
        return roi

    def delete_roi(self, *, roi_id: int, user_id: int) -> bool:
        with SessionLocal() as db:
            roi = (
                db.query(ROI)
                .join(Video, Video.id == ROI.video_id)
                .filter(ROI.id == roi_id, Video.uploaded_by == user_id)
                .first()
            )
            if not roi:
                return False
            db.delete(roi)
            db.commit()
        audit_service.log(user_id=user_id, action="ROI_DELETE", entity_type="roi", entity_id=str(roi_id))
        return True


roi_service = ROIServices()

