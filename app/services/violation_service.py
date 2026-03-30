from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.analysis_run import AnalysisRun
from app.models.roi import ROI
from app.models.violation import Violation
from app.models.video import Video
from app.utils.frame_extractor import save_evidence_frame
from app.utils.geometry import calculate_iou, get_bottom_center, point_in_polygon


logger = logging.getLogger("cypath_lite.services.violation_service")


def _normalize_vehicle_class(class_name: str) -> str:
    cn = (class_name or "").lower()
    if "car" in cn:
        return "car"
    if "bus" in cn:
        return "bus"
    if "truck" in cn:
        return "truck"
    if "motor" in cn and ("cycle" in cn or "bike" in cn):
        return "motorcycle"
    return class_name


def violates_roi(
    *,
    bounding_box: Sequence[float],
    roi_polygon: Sequence[Sequence[float]],
    method: str,
    overlap_threshold: Optional[float] = None,
) -> bool:
    if method == "BOTTOM_CENTER":
        bottom_center = get_bottom_center(bounding_box)
        return point_in_polygon(bottom_center, roi_polygon)
    if method == "OVERLAP":
        thr = float(overlap_threshold or 0.5)
        return calculate_iou(bounding_box, roi_polygon) >= thr
    return False


@dataclass
class ViolationPersistenceState:
    streak: int = 0
    recorded_for_streak: bool = False
    last_violation_frame_index: Optional[int] = None


class ViolationService:
    def list_violations(self, *, run_id: int, user_id: int) -> list[Violation]:
        with SessionLocal() as db:
            return (
                db.query(Violation)
                .join(AnalysisRun, AnalysisRun.id == Violation.run_id)
                .join(Video, Video.id == AnalysisRun.video_id)
                .filter(Violation.run_id == run_id, Video.uploaded_by == user_id)
                .order_by(Violation.time_sec.asc())
                .all()
            )

    def get_violation(self, *, violation_id: int, user_id: int) -> Optional[Violation]:
        with SessionLocal() as db:
            return (
                db.query(Violation)
                .join(AnalysisRun, AnalysisRun.id == Violation.run_id)
                .join(Video, Video.id == AnalysisRun.video_id)
                .filter(Violation.id == violation_id, Video.uploaded_by == user_id)
                .first()
            )

    def detect_and_persist(
        self,
        *,
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        roi_polygon: Sequence[Sequence[float]],
        method: str,
        overlap_threshold: Optional[float],
        persistence_frames: int,
        run: AnalysisRun,
        frame_index: int,
        time_sec: float,
        evidence_dir: Path,
        state: ViolationPersistenceState,
    ) -> int:
        """
        Returns number of violations created for this frame (0 or 1).
        """
        violation_candidates: list[dict[str, Any]] = []
        for det in detections:
            bbox = det.get("bounding_box")
            if not bbox:
                continue
            if violates_roi(
                bounding_box=bbox,
                roi_polygon=roi_polygon,
                method=method,
                overlap_threshold=overlap_threshold,
            ):
                violation_candidates.append(det)

        if violation_candidates:
            state.streak += 1
            state.last_violation_frame_index = frame_index
        else:
            state.streak = 0
            state.recorded_for_streak = False
            return 0

        if state.streak < persistence_frames or state.recorded_for_streak:
            return 0

        # Confirmed violation for this streak: record the top candidate.
        top = sorted(violation_candidates, key=lambda d: float(d.get("confidence", 0.0)), reverse=True)[0]
        bbox = top["bounding_box"]
        vehicle_class = _normalize_vehicle_class(top.get("vehicle_class") or "vehicle")
        confidence = float(top.get("confidence", 0.0))
        evidence_dir.mkdir(parents=True, exist_ok=True)
        label = f"VIOLATION: {vehicle_class}"
        evidence_path = evidence_dir / f"run_{run.id}_frame_{frame_index}.jpg"

        # Evidence overlays
        save_evidence_frame(
            frame,
            output_path=evidence_path,
            roi_polygon=roi_polygon,
            bounding_box=bbox,
            label=label,
        )

        with SessionLocal() as db:
            v = Violation(
                run_id=run.id,
                time_sec=time_sec,
                frame_index=frame_index,
                vehicle_class=vehicle_class,
                confidence=confidence,
                bounding_box=list(map(float, bbox)),
                evidence_path=str(evidence_path),
            )
            db.add(v)
            db.commit()
        state.recorded_for_streak = True
        return 1


violation_service = ViolationService()

