from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
from sqlalchemy import and_

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.roi import ROI
from app.models.video import Video
from app.schemas.run import RunCreateInput, RunStatus
from app.services.audit_service import audit_service


logger = logging.getLogger("cypath_lite.services.detection_service")


class DetectionService:
    def __init__(self) -> None:
        self._model: Any | None = None
        self._model_names: dict[int, str] = {}

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO  # lazy import

            self._model = YOLO(settings.model_path)
            # ultralytics sets model.names as dict[int,str]
            names = getattr(self._model, "names", None)
            if isinstance(names, dict):
                self._model_names = {int(k): str(v) for k, v in names.items()}
        except Exception:
            # In test/dev environments the model file may be missing; keep service usable.
            logger.warning("YOLO model could not be loaded. Detections will be empty.", exc_info=True)
            self._model = None
            self._model_names = {}

    def detect(self, frame: np.ndarray, *, confidence_threshold: float) -> list[dict[str, Any]]:
        self._load_model()
        if self._model is None:
            return []

        # ultralytics returns Results; run single-image predict
        results = self._model.predict(frame, conf=confidence_threshold, verbose=False)
        if not results:
            return []
        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        detections: list[dict[str, Any]] = []
        for b in boxes:
            # b.xyxy: tensor shape [1,4], b.conf and b.cls
            xyxy = b.xyxy[0].tolist()
            conf = float(b.conf[0].item()) if hasattr(b.conf, "__len__") else float(b.conf.item())
            cls_id = int(b.cls[0].item()) if hasattr(b.cls, "__len__") else int(b.cls.item())
            class_name = self._model_names.get(cls_id, str(cls_id))
            detections.append(
                {
                    "bounding_box": [float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])],
                    "vehicle_class": class_name,
                    "confidence": conf,
                    "class_id": cls_id,
                }
            )
        return detections

    def _run_access_filter(self, *, user_id: int):
        return and_(Video.uploaded_by == user_id)

    def create_analysis_run(self, *, payload: RunCreateInput, created_by: int) -> AnalysisRun:
        with SessionLocal() as db:
            # Validate referenced ROI exists
            roi = db.query(ROI).filter(ROI.id == payload.roi_id).first()
            if not roi:
                raise ValueError("ROI not found")
            if roi.video_id != payload.video_id:
                raise ValueError("ROI does not belong to the specified video")

            video = db.query(Video).filter(Video.id == payload.video_id, Video.uploaded_by == created_by).first()
            if not video:
                raise ValueError("Video not found or not owned by user")

            run = AnalysisRun(
                video_id=payload.video_id,
                roi_id=payload.roi_id,
                status="QUEUED",
                model_name="yolov8n",
                sample_fps=payload.sample_fps,
                confidence_threshold=payload.confidence_threshold,
                persistence_frames=payload.persistence_frames,
                resize_width=payload.resize_width,
                resize_height=payload.resize_height,
                intrusion_method=payload.intrusion_method,
                overlap_threshold=payload.overlap_threshold,
                total_frames=0,
                processed_frames=0,
                total_violations=0,
                progress_percentage=0.0,
                created_by=created_by,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
        audit_service.log(user_id=created_by, action="RUN_CREATE", entity_type="analysis_run", entity_id=str(run.id))
        return run

    def list_runs(
        self,
        *,
        status: Optional[RunStatus],
        video_id: Optional[int],
        user_id: int,
    ) -> list[AnalysisRun]:
        with SessionLocal() as db:
            q = db.query(AnalysisRun).join(Video, Video.id == AnalysisRun.video_id).filter(Video.uploaded_by == user_id)
            if status:
                q = q.filter(AnalysisRun.status == status)
            if video_id:
                q = q.filter(AnalysisRun.video_id == video_id)
            return q.order_by(AnalysisRun.created_at.desc()).all()

    def get_run(self, *, run_id: int, user_id: int) -> Optional[AnalysisRun]:
        with SessionLocal() as db:
            return (
                db.query(AnalysisRun)
                .join(Video, Video.id == AnalysisRun.video_id)
                .filter(AnalysisRun.id == run_id, Video.uploaded_by == user_id)
                .first()
            )

    def cancel_run(self, *, run_id: int, user_id: int) -> Optional[AnalysisRun]:
        with SessionLocal() as db:
            run = (
                db.query(AnalysisRun)
                .join(Video, Video.id == AnalysisRun.video_id)
                .filter(AnalysisRun.id == run_id, Video.uploaded_by == user_id)
                .first()
            )
            if not run:
                return None

            if run.status in {"COMPLETED", "FAILED"}:
                return run
            run.status = "FAILED"
            run.error_message = "Cancelled"
            db.commit()
            db.refresh(run)
        audit_service.log(user_id=user_id, action="RUN_CANCEL", entity_type="analysis_run", entity_id=str(run.id))
        return run


detection_service = DetectionService()

