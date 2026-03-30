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
async def test_register_and_login():
    _setup_test_env()

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.core.database import Base, engine
    from app.main import app

    db_path = Path("test_cypath.db")
    if db_path.exists():
        db_path.unlink()

    Base.metadata.create_all(bind=engine)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = "user_auth_test@example.com"
        password = "password123"

        reg = await ac.post(
            "/auth/register",
            json={"full_name": "Test User", "email": email, "password": password, "role": "ANALYST"},
        )
        assert reg.status_code == 201
        assert reg.json()["email"] == email

        login = await ac.post(
            "/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login.status_code == 200
        body = login.json()
        assert "access_token" in body

