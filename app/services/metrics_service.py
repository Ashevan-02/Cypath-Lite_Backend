from __future__ import annotations

from app.core.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.ground_truth import GroundTruth
from app.models.video import Video
from app.models.violation import Violation
from app.schemas.metrics import DetectionMetricsResponse, GroundTruthCreate, GroundTruthResponse


# A detected violation frame is considered a true positive if it falls within
# this many frames of a ground truth annotation.
FRAME_TOLERANCE = 5


class MetricsService:
    def add_ground_truth(
        self, *, run_id: int, entries: list[GroundTruthCreate], user_id: int
    ) -> list[GroundTruthResponse]:
        with SessionLocal() as db:
            run = (
                db.query(AnalysisRun)
                .join(Video, Video.id == AnalysisRun.video_id)
                .filter(AnalysisRun.id == run_id, Video.uploaded_by == user_id)
                .first()
            )
            if not run:
                raise ValueError("Run not found")

            records = [
                GroundTruth(
                    run_id=run_id,
                    frame_index=e.frame_index,
                    time_sec=e.time_sec,
                    created_by=user_id,
                )
                for e in entries
            ]
            db.add_all(records)
            db.commit()
            for r in records:
                db.refresh(r)
            return [GroundTruthResponse.model_validate(r) for r in records]

    def list_ground_truth(self, *, run_id: int, user_id: int) -> list[GroundTruthResponse]:
        with SessionLocal() as db:
            run = (
                db.query(AnalysisRun)
                .join(Video, Video.id == AnalysisRun.video_id)
                .filter(AnalysisRun.id == run_id, Video.uploaded_by == user_id)
                .first()
            )
            if not run:
                raise ValueError("Run not found")
            records = db.query(GroundTruth).filter(GroundTruth.run_id == run_id).all()
            return [GroundTruthResponse.model_validate(r) for r in records]

    def compute_metrics(self, *, run_id: int, user_id: int) -> DetectionMetricsResponse:
        with SessionLocal() as db:
            run = (
                db.query(AnalysisRun)
                .join(Video, Video.id == AnalysisRun.video_id)
                .filter(AnalysisRun.id == run_id, Video.uploaded_by == user_id)
                .first()
            )
            if not run:
                raise ValueError("Run not found")
            if run.status != "COMPLETED":
                raise ValueError("Run must be COMPLETED before computing metrics")

            gt_frames = [
                r.frame_index
                for r in db.query(GroundTruth).filter(GroundTruth.run_id == run_id).all()
            ]
            detected_frames = [
                v.frame_index
                for v in db.query(Violation).filter(Violation.run_id == run_id).all()
            ]

        if not gt_frames:
            raise ValueError("No ground truth annotations found for this run. Add ground truth first via POST /runs/{run_id}/ground-truth")

        # Match each ground truth to at most one detection within tolerance
        matched_gt = set()
        matched_det = set()

        for di, det_f in enumerate(detected_frames):
            for gi, gt_f in enumerate(gt_frames):
                if gi in matched_gt:
                    continue
                if abs(det_f - gt_f) <= FRAME_TOLERANCE:
                    matched_gt.add(gi)
                    matched_det.add(di)
                    break

        tp = len(matched_gt)
        fp = len(detected_frames) - len(matched_det)
        fn = len(gt_frames) - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        # Accuracy = TP / (TP + FP + FN)  — standard for detection tasks
        accuracy = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0

        return DetectionMetricsResponse(
            run_id=run_id,
            total_ground_truth=len(gt_frames),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            accuracy=round(accuracy, 4),
        )


metrics_service = MetricsService()
