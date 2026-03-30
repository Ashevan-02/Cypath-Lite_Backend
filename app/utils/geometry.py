from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import numpy as np


Point = Tuple[float, float]
Polygon = Sequence[Point]


def get_bottom_center(bounding_box: Sequence[float]) -> Point:
    x1, y1, x2, y2 = bounding_box
    return ((x1 + x2) / 2.0, y2)


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """
    Ray casting algorithm for point-in-polygon.
    """
    x, y = point
    inside = False
    n = len(polygon)
    if n < 3:
        return False

    x0, y0 = polygon[-1]
    for i in range(n):
        x1, y1 = polygon[i]
        intersects = (y1 > y) != (y0 > y) and (x < (x0 - x1) * (y - y1) / (y0 - y1 + 1e-12) + x1)
        if intersects:
            inside = not inside
        x0, y0 = x1, y1
    return inside


def calculate_iou(box: Sequence[float], polygon: Polygon) -> float:
    """
    Approximate IoU between a bounding box and ROI polygon by rasterization.
    """
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1 or len(polygon) < 3:
        return 0.0

    # Create a local canvas to keep computation bounded.
    poly_x = [p[0] for p in polygon]
    poly_y = [p[1] for p in polygon]

    min_x = int(max(0, min(min(poly_x), x1)))
    min_y = int(max(0, min(min(poly_y), y1)))
    max_x = int(max(max(poly_x), x2))
    max_y = int(max(max(poly_y), y2))

    width = max(1, max_x - min_x + 1)
    height = max(1, max_y - min_y + 1)

    canvas_poly = np.zeros((height, width), dtype=np.uint8)
    canvas_box = np.zeros((height, width), dtype=np.uint8)

    # Polygon mask
    pts = np.array([[(px - min_x), (py - min_y)] for px, py in polygon], dtype=np.int32)
    # Simple fill using cv2 if available; otherwise fallback to bbox approximation.
    try:
        import cv2  # local import

        cv2.fillPoly(canvas_poly, [pts], 1)
        canvas_box[int(y1 - min_y) : int(y2 - min_y), int(x1 - min_x) : int(x2 - min_x)] = 1
    except Exception:
        # Fallback: IoU of bounding boxes (less accurate but safe).
        poly_bbox_x1, poly_bbox_y1 = min(poly_x), min(poly_y)
        poly_bbox_x2, poly_bbox_y2 = max(poly_x), max(poly_y)
        inter_x1 = max(x1, poly_bbox_x1)
        inter_y1 = max(y1, poly_bbox_y1)
        inter_x2 = min(x2, poly_bbox_x2)
        inter_y2 = min(y2, poly_bbox_y2)
        inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
        box_area = (x2 - x1) * (y2 - y1)
        poly_area = (poly_bbox_x2 - poly_bbox_x1) * (poly_bbox_y2 - poly_bbox_y1)
        union = box_area + poly_area - inter_area
        return float(inter_area / union) if union > 0 else 0.0

    inter = int(np.logical_and(canvas_poly == 1, canvas_box == 1).sum())
    union = int(np.logical_or(canvas_poly == 1, canvas_box == 1).sum())
    return float(inter / union) if union > 0 else 0.0

