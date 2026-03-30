from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "CyPath Lite API"
    debug: bool = True
    secret_key: str

    # Database
    database_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 1440

    # Storage
    storage_path: str = "./storage"
    max_upload_size_mb: int = 500
    allowed_video_extensions: str = "mp4,mov,avi,mkv"
    allowed_image_extensions: str = "jpg,jpeg,png,bmp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Model Settings
    model_path: str = "./models/yolov8n.pt"
    default_confidence_threshold: float = 0.5
    default_sample_fps: int = 5
    default_persistence_frames: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # --- Path helpers ---

    @property
    def storage_root(self) -> Path:
        return Path(self.storage_path)

    @property
    def videos_dir(self) -> Path:
        return self.storage_root / "videos"

    @property
    def frames_dir(self) -> Path:
        return self.storage_root / "frames"

    @property
    def evidence_dir(self) -> Path:
        return self.storage_root / "evidence"

    @property
    def reports_dir(self) -> Path:
        return self.storage_root / "reports"

    @property
    def images_dir(self) -> Path:
        return self.storage_root / "images"

    # --- Extension helpers ---

    @property
    def allowed_video_extension_set(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_video_extensions.split(",")}

    @property
    def allowed_image_extension_set(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_image_extensions.split(",")}

    @property
    def allowed_extension_set(self) -> set[str]:
        return self.allowed_video_extension_set | self.allowed_image_extension_set


settings = Settings()
