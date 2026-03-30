from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import magic


def validate_file_extension(*, filename: str, allowed_extensions: Iterable[str]) -> None:
    suffix = Path(filename).suffix.lower().lstrip(".")
    allowed = {ext.lower().lstrip(".") for ext in allowed_extensions}
    if suffix not in allowed:
        raise ValueError(f"Invalid file extension .{suffix}. Allowed: {sorted(allowed)}")


def validate_file_size(*, file_size: int, max_size_mb: int) -> None:
    max_bytes = int(max_size_mb * 1024 * 1024)
    if file_size > max_bytes:
        raise ValueError(f"File too large. Max is {max_size_mb} MB")


def validate_video_file(file_path: str | os.PathLike[str]) -> None:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValueError("Uploaded file not found for validation")
    m = magic.Magic(mime=True)
    mime_type = m.from_file(str(path))
    if not mime_type or not mime_type.startswith("video/"):
        raise ValueError(f"Invalid video file (detected MIME: {mime_type})")


def validate_image_file(file_path: str | os.PathLike[str]) -> None:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise ValueError("Uploaded file not found for validation")
    m = magic.Magic(mime=True)
    mime_type = m.from_file(str(path))
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"Invalid image file (detected MIME: {mime_type})")


def detect_media_type(file_path: str | os.PathLike[str]) -> str:
    """Returns 'video' or 'image' based on MIME type."""
    m = magic.Magic(mime=True)
    mime_type = m.from_file(str(file_path))
    if mime_type and mime_type.startswith("video/"):
        return "video"
    if mime_type and mime_type.startswith("image/"):
        return "image"
    raise ValueError(f"Unsupported media type (detected MIME: {mime_type})")
