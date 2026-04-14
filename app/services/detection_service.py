from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import SessionLocal
from app.core.security import Roles
from app.models.analysis_run import AnalysisRun
from app.models.roi import ROI
from app.models.video import Video

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None


class DetectionService:
    def __init__(self) -> None:
        self.vehicle_classes = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
        self.model = None
        if YOLO is not None:
            try:
                # Keep startup resilient even if weights are not present.
                self.model = YOLO("yolov8n.pt")
            except Exception:
                self.model = None

    def detect(self, frame: Any, confidence_threshold: float = 0.5) -> list[dict[str, Any]]:
        """Detect vehicles and normalize output for downstream violation service."""
        if self.model is None:
            return []

        results = self.model(frame, conf=confidence_threshold)
        vehicles: list[dict[str, Any]] = []
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            if class_id not in self.vehicle_classes:
                continue
            xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
            x1, y1, x2, y2 = xyxy
            vehicles.append(
                {
                    "vehicle_type": self.vehicle_classes[class_id],
                    "confidence": float(box.conf[0]),
                    "bounding_box": [float(x1), float(y1), float(x2), float(y2)],
                    "bottom_center": [float((x1 + x2) / 2), float(y2)],
                }
            )
        return vehicles

    # Backward-compatible alias used by older modules.
    def detect_vehicles(self, frame: Any, confidence_threshold: float = 0.5) -> list[dict[str, Any]]:
        return self.detect(frame=frame, confidence_threshold=confidence_threshold)

    def create_analysis_run(self, payload: Any, created_by: int) -> AnalysisRun:
        with SessionLocal() as db:
            video = db.query(Video).filter(Video.id == payload.video_id).first()
            roi = db.query(ROI).filter(ROI.id == payload.roi_id).first()
            if not video:
                raise ValueError("Video not found")
            if not roi:
                raise ValueError("ROI not found")
            if roi.video_id != video.id:
                raise ValueError("ROI does not belong to selected video")

            run = AnalysisRun(
                video_id=payload.video_id,
                roi_id=payload.roi_id,
                status="QUEUED",
                model_name=getattr(payload, "model_name", "yolov8n"),
                sample_fps=payload.sample_fps,
                confidence_threshold=payload.confidence_threshold,
                persistence_frames=payload.persistence_frames,
                resize_width=getattr(payload, "resize_width", None),
                resize_height=getattr(payload, "resize_height", None),
                intrusion_method=payload.intrusion_method,
                overlap_threshold=getattr(payload, "overlap_threshold", None),
                total_frames=0,
                processed_frames=0,
                total_violations=0,
                progress_percentage=0.0,
                created_by=created_by,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            return run

    def list_runs(self, status: Optional[str], video_id: Optional[int], user_id: int) -> list[AnalysisRun]:
        with SessionLocal() as db:
            query = db.query(AnalysisRun)

            # Restrict non-admin users to their own runs.
            from app.models.user import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user or user.role != Roles.ADMIN:
                query = query.filter(AnalysisRun.created_by == user_id)

            if status:
                query = query.filter(AnalysisRun.status == status)
            if video_id:
                query = query.filter(AnalysisRun.video_id == video_id)
            return query.order_by(AnalysisRun.created_at.desc()).all()

    def get_run(self, run_id: int, user_id: int) -> Optional[AnalysisRun]:
        with SessionLocal() as db:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if not run:
                return None
            from app.models.user import User

            user = db.query(User).filter(User.id == user_id).first()
            if user and user.role == Roles.ADMIN:
                return run
            return run if run.created_by == user_id else None

    def cancel_run(self, run_id: int, user_id: int) -> Optional[AnalysisRun]:
        with SessionLocal() as db:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if not run:
                return None
            from app.models.user import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            if user.role != Roles.ADMIN and run.created_by != user_id:
                return None

            if run.status in {"COMPLETED", "FAILED"}:
                return run

            run.status = "FAILED"
            run.error_message = "Cancelled by user"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            return run


detection_service = DetectionService()