from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.video import Video
from app.utils.file_validator import validate_file_extension, validate_file_size, detect_media_type
from app.utils.frame_extractor import get_video_metadata
from app.services.audit_service import audit_service


logger = logging.getLogger("cypath_lite.services.video_service")


class VideoService:
    def upload_video(
        self,
        *,
        file: UploadFile,
        uploaded_by: int,
        location_label: Optional[str],
        camera_type: Optional[str],
        captured_at: Optional[datetime],
    ) -> Video:
        if not file.filename:
            raise ValueError("No file name provided")

        validate_file_extension(filename=file.filename, allowed_extensions=settings.allowed_extension_set)

        # Stream to a temp file with explicit size enforcement.
        storage_tmp_dir = settings.storage_root / ".tmp_uploads"
        storage_tmp_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(file.filename).suffix
        tmp_name = f"upload_{uuid.uuid4().hex}{suffix}"
        tmp_path = storage_tmp_dir / tmp_name

        size_bytes = 0
        try:
            with tmp_path.open("wb") as f:
                while True:
                    chunk = file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > int(settings.max_upload_size_mb * 1024 * 1024):
                        raise ValueError("File too large")
                    f.write(chunk)

            validate_file_size(file_size=size_bytes, max_size_mb=settings.max_upload_size_mb)
            media_type = detect_media_type(tmp_path)

            storage_dir = settings.videos_dir if media_type == "video" else settings.images_dir
            unique_name = f"{uuid.uuid4().hex}{suffix}"
            final_path = storage_dir / unique_name
            final_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(tmp_path), str(final_path))
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            raise

        with SessionLocal() as db:
            video = Video(
                filename=file.filename,
                storage_path=str(final_path),
                media_type=media_type,
                file_size=size_bytes,
                duration_seconds=None,
                resolution=None,
                location_label=location_label,
                camera_type=camera_type,
                captured_at=captured_at,
                uploaded_by=uploaded_by,
            )
            db.add(video)
            try:
                db.commit()
            except IntegrityError as e:
                db.rollback()
                raise ValueError("Failed to save video metadata") from e
            db.refresh(video)
        audit_service.log(user_id=uploaded_by, action="VIDEO_UPLOAD", entity_type="video", entity_id=str(video.id))
        return video

    def list_videos(self, *, user_id: int) -> list[Video]:
        with SessionLocal() as db:
            return db.query(Video).filter(Video.uploaded_by == user_id).order_by(Video.created_at.desc()).all()

    def get_video(self, *, video_id: int, user_id: int) -> Optional[Video]:
        with SessionLocal() as db:
            return (
                db.query(Video)
                .filter(Video.id == video_id, Video.uploaded_by == user_id)
                .first()
            )

    def delete_video(self, *, video_id: int, user_id: int) -> bool:
        with SessionLocal() as db:
            video = db.query(Video).filter(Video.id == video_id, Video.uploaded_by == user_id).first()
            if not video:
                return False
            db.delete(video)
            db.commit()

        # Remove file after DB deletion.
        try:
            p = Path(video.storage_path)
            if p.exists():
                p.unlink()
        except Exception:
            logger.warning("Failed deleting video file from storage.", exc_info=True)

        audit_service.log(user_id=user_id, action="VIDEO_DELETE", entity_type="video", entity_id=str(video_id))
        return True

    def get_video_metadata(self, *, video_id: int, user_id: int) -> Optional[dict[str, object]]:
        with SessionLocal() as db:
            video = db.query(Video).filter(Video.id == video_id, Video.uploaded_by == user_id).first()
            if not video:
                return None

            meta = get_video_metadata(video.storage_path)
            video.duration_seconds = meta.get("duration_seconds")
            video.resolution = meta.get("resolution")
            db.commit()

            return {
                "duration_seconds": video.duration_seconds,
                "resolution": video.resolution,
                "file_size": video.file_size,
                "captured_at": video.captured_at,
                "location_label": video.location_label,
                "camera_type": video.camera_type,
            }


video_service = VideoService()

