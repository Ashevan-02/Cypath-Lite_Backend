from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from app.core.database import SessionLocal
from app.core.security import Roles
from app.models.analysis_run import AnalysisRun
from app.models.video import Video
from app.models.violation import Violation


def _as_polygon_array(roi_polygon: list[list[float]] | list[dict[str, float]]) -> np.ndarray:
    points: list[list[float]] = []
    for p in roi_polygon or []:
        if isinstance(p, dict):
            points.append([float(p.get("x", 0.0)), float(p.get("y", 0.0))])
        else:
            points.append([float(p[0]), float(p[1])])
    return np.array(points, dtype=np.float32)


def violates_roi(
    *,
    bounding_box: list[float],
    roi_polygon: list[list[float]] | list[dict[str, float]],
    method: str,
    overlap_threshold: Optional[float] = None,
) -> bool:
    if not bounding_box or len(bounding_box) != 4 or not roi_polygon:
        return False

    poly = _as_polygon_array(roi_polygon)
    x1, y1, x2, y2 = [float(v) for v in bounding_box]
    bottom_center = ((x1 + x2) / 2.0, y2)

    if method == "BOTTOM_CENTER":
        return cv2.pointPolygonTest(poly, bottom_center, False) >= 0

    # OVERLAP approximation: check ratio of bbox corners/center points inside polygon.
    sample_points = [
        (x1, y1),
        (x2, y1),
        (x1, y2),
        (x2, y2),
        ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
    ]
    inside = sum(1 for pt in sample_points if cv2.pointPolygonTest(poly, pt, False) >= 0)
    ratio = inside / len(sample_points)
    return ratio >= float(overlap_threshold or 0.3)


@dataclass
class ViolationPersistenceState:
    consecutive_hits: dict[tuple[int, int], int] = field(default_factory=dict)


class ViolationService:
    def list_violations(self, *, run_id: int, user_id: int) -> list[Violation]:
        with SessionLocal() as db:
            run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if not run:
                return []
            from app.models.user import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return []
            if user.role != Roles.ADMIN and run.created_by != user_id:
                return []
            return db.query(Violation).filter(Violation.run_id == run_id).order_by(Violation.frame_index.asc()).all()

    def get_violation(self, *, violation_id: int, user_id: int) -> Optional[Violation]:
        with SessionLocal() as db:
            violation = db.query(Violation).filter(Violation.id == violation_id).first()
            if not violation:
                return None
            run = db.query(AnalysisRun).filter(AnalysisRun.id == violation.run_id).first()
            if not run:
                return None
            from app.models.user import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            if user.role != Roles.ADMIN and run.created_by != user_id:
                return None
            return violation

    def flag_false_positive(self, *, violation_id: int, user_id: int) -> Optional[Violation]:
        with SessionLocal() as db:
            v = db.query(Violation).filter(Violation.id == violation_id).first()
            if not v:
                return None
            run = db.query(AnalysisRun).filter(AnalysisRun.id == v.run_id).first()
            from app.models.user import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user or not run:
                return None
            if user.role != Roles.ADMIN and run.created_by != user_id:
                return None
            v.is_false_positive = True
            db.commit()
            db.refresh(v)
            return v

    def verify_violation(self, *, violation_id: int, user_id: int) -> Optional[Violation]:
        with SessionLocal() as db:
            v = db.query(Violation).filter(Violation.id == violation_id).first()
            if not v:
                return None
            run = db.query(AnalysisRun).filter(AnalysisRun.id == v.run_id).first()
            from app.models.user import User

            user = db.query(User).filter(User.id == user_id).first()
            if not user or not run:
                return None
            if user.role != Roles.ADMIN and run.created_by != user_id:
                return None
            v.verified = True
            db.commit()
            db.refresh(v)
            return v

    def detect_and_persist(
        self,
        *,
        frame: Any,
        detections: list[dict[str, Any]],
        roi_polygon: list[list[float]] | list[dict[str, float]],
        method: str,
        overlap_threshold: Optional[float],
        persistence_frames: int,
        run: AnalysisRun,
        frame_index: int,
        time_sec: float,
        evidence_dir: Path,
        state: ViolationPersistenceState,
    ) -> int:
        created = 0
        persistence_frames = max(1, int(persistence_frames or 1))
        evidence_dir.mkdir(parents=True, exist_ok=True)

        for idx, det in enumerate(detections):
            bbox = det.get("bounding_box")
            if not bbox:
                continue
            if not violates_roi(
                bounding_box=bbox,
                roi_polygon=roi_polygon,
                method=method,
                overlap_threshold=overlap_threshold,
            ):
                continue

            key = (frame_index, idx)
            state.consecutive_hits[key] = state.consecutive_hits.get(key, 0) + 1
            if state.consecutive_hits[key] < persistence_frames:
                continue

            evidence_name = f"run_{run.id}_frame_{frame_index}_{idx}.jpg"
            evidence_file = evidence_dir / evidence_name
            try:
                cv2.imwrite(str(evidence_file), frame)
            except Exception:
                evidence_file = None

            v = Violation(
                run_id=run.id,
                time_sec=float(time_sec),
                frame_index=int(frame_index),
                vehicle_class=str(det.get("vehicle_type", "vehicle")),
                confidence=float(det.get("confidence", 0.0)),
                bounding_box=bbox,
                evidence_path=str(evidence_file) if evidence_file else None,
                is_false_positive=False,
                verified=False,
            )
            # run is already attached to a session in worker; add through same session.
            from sqlalchemy.orm import object_session

            sess = object_session(run)
            if sess is not None:
                sess.add(v)
            created += 1

        return created


violation_service = ViolationService()