import os

import pytest
from httpx import ASGITransport, AsyncClient
from pathlib import Path


def _setup_test_env():
    os.environ.setdefault("APP_NAME", "CyPath Lite API")
    os.environ.setdefault("DEBUG", "True")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_cypath.db")
    os.environ.setdefault("JWT_SECRET_KEY", "jwt-test-secret")
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("JWT_EXPIRY_MINUTES", "60")
    os.environ.setdefault("STORAGE_PATH", "./storage")
    os.environ.setdefault("MAX_UPLOAD_SIZE_MB", "10")
    os.environ.setdefault("ALLOWED_VIDEO_EXTENSIONS", "mp4,mov,avi,mkv")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("MODEL_PATH", "./models/yolov8n.pt")
    os.environ.setdefault("DEFAULT_CONFIDENCE_THRESHOLD", "0.5")
    os.environ.setdefault("DEFAULT_SAMPLE_FPS", "5")
    os.environ.setdefault("DEFAULT_PERSISTENCE_FRAMES", "3")


@pytest.mark.asyncio
async def test_run_creation_and_status(monkeypatch):
    _setup_test_env()

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.core.database import Base, engine
    from app.main import app

    db_path = Path("test_cypath.db")
    if db_path.exists():
        db_path.unlink()

    Base.metadata.create_all(bind=engine)

    # Bypass MIME validation for upload
    import app.services.video_service as video_service_module

    monkeypatch.setattr(video_service_module, "validate_video_file", lambda _: None)

    # Ensure ROI validation has frame dimensions
    import app.services.roi_service as roi_service_module

    monkeypatch.setattr(
        roi_service_module,
        "get_video_metadata",
        lambda _path: {"resolution": "640x480", "duration_seconds": 0.0, "fps": 30.0, "frame_count": 0},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = "user_runs_test@example.com"
        password = "password123"

        reg = await ac.post(
            "/auth/register",
            json={"full_name": "Test Runs User", "email": email, "password": password, "role": "ANALYST"},
        )
        assert reg.status_code == 201

        login = await ac.post(
            "/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        upload = await ac.post(
            "/videos/upload",
            headers=headers,
            files={"file": ("test.mp4", b"not-a-real-video", "video/mp4")},
        )
        assert upload.status_code == 201
        video_id = upload.json()["id"]

        roi = await ac.post(
            f"/videos/{video_id}/roi",
            headers=headers,
            json={"polygon": [{"x": 10, "y": 10}, {"x": 200, "y": 10}, {"x": 10, "y": 200}]},
        )
        assert roi.status_code == 201
        roi_id = roi.json()["id"]

        run = await ac.post(
            "/runs",
            headers=headers,
            json={
                "video_id": video_id,
                "roi_id": roi_id,
                "sample_fps": 1,
                "confidence_threshold": 0.5,
                "persistence_frames": 2,
                "intrusion_method": "BOTTOM_CENTER",
            },
        )
        assert run.status_code == 201
        run_body = run.json()
        assert run_body["status"] == "QUEUED"
        run_id = run_body["id"]

        status_resp = await ac.get(f"/runs/{run_id}/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "QUEUED"

