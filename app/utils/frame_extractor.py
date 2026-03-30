from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np


def get_video_metadata(video_path: str | os.PathLike[str]) -> dict[str, object]:
    import cv2  # lazy import

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not open video file for metadata extraction")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    duration_seconds = float(frame_count / fps) if fps > 0 else 0.0
    resolution = f"{width}x{height}" if width and height else None

    cap.release()
    return {
        "duration_seconds": duration_seconds,
        "fps": fps,
        "resolution": resolution,
        "frame_count": frame_count,
    }


def extract_frames(
    video_path: str | os.PathLike[str],
    *,
    sample_fps: int,
    resize_dimensions: Optional[tuple[int, int]] = None,
    output_dir: str | os.PathLike[str],
) -> List[tuple[int, float, str]]:
    """
    Extract sampled frames and save them to disk.

    Returns list of (frame_index, time_sec, saved_frame_path).
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    import cv2  # lazy import

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not open video file for frame extraction")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0 or frame_count <= 0:
        cap.release()
        raise ValueError("Invalid video metadata for frame extraction")

    step = max(1, int(round(fps / float(sample_fps))))

    saved: List[tuple[int, float, str]] = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if idx % step == 0:
            if resize_dimensions:
                frame = cv2.resize(frame, resize_dimensions)
            time_sec = float(idx / fps) if fps > 0 else 0.0
            name = f"frame_{idx}_{uuid.uuid4().hex}.jpg"
            file_path = output_path / name
            cv2.imwrite(str(file_path), frame)
            saved.append((idx, time_sec, str(file_path)))

        idx += 1

    cap.release()
    return saved


def save_evidence_frame(
    frame: np.ndarray,
    *,
    output_path: str | os.PathLike[str],
    roi_polygon: Sequence[Sequence[float]],
    bounding_box: Sequence[float],
    label: str,
) -> str:
    """
    Save an evidence frame with overlays.
    """
    import cv2  # lazy import

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    img = frame.copy()
    # ROI polygon
    pts = np.array([[float(x), float(y)] for x, y in roi_polygon], dtype=np.int32)
    if len(pts) >= 3:
        cv2.polylines(img, [pts], isClosed=True, color=(0, 255, 255), thickness=2)

    # Bounding box
    x1, y1, x2, y2 = map(int, bounding_box)
    cv2.rectangle(img, (x1, y1), (x2, y2), color=(0, 255, 0), thickness=2)

    # Label background
    text = label
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
    y_text = max(0, y1 - 10)
    cv2.rectangle(img, (x1, y_text - th - baseline), (x1 + tw + 2, y_text + baseline), (0, 255, 0), -1)
    cv2.putText(img, text, (x1 + 1, y_text - baseline), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    cv2.imwrite(str(out), img)
    return str(out)

