from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.metrics import router as metrics_router
from app.api.endpoints.reports import router as reports_router
from app.api.endpoints.roi import router as roi_router
from app.api.endpoints.runs import router as runs_router
from app.api.endpoints.users import router as users_router
from app.api.endpoints.violations import router as violations_router
from app.api.endpoints.videos import router as videos_router
from app.api.middleware.auth import JWTAuthMiddleware
from app.core.config import settings


def _configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_logging()
    # Ensure storage folders exist
    for p in (settings.videos_dir, settings.frames_dir, settings.evidence_dir, settings.reports_dir, settings.images_dir):
        p.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        openapi_tags=[
            {"name": "auth", "description": "Authentication endpoints"},
            {"name": "users", "description": "Admin user management"},
            {"name": "videos", "description": "Video upload and metadata"},
            {"name": "roi", "description": "ROI polygon management"},
            {"name": "runs", "description": "Analysis run lifecycle"},
            {"name": "violations", "description": "Violations and analytics"},
            {"name": "reports", "description": "Report generation and download"},
            {"name": "metrics", "description": "Ground truth management and detection performance metrics"},
        ],
        lifespan=lifespan,
    )

    # Development-friendly CORS (allow all). Restrict origins in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JWTAuthMiddleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": "Request validation failed", "errors": exc.errors()},
        )

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(videos_router)
    app.include_router(roi_router)
    app.include_router(runs_router)
    app.include_router(violations_router)
    app.include_router(reports_router)
    app.include_router(metrics_router)
    return app


app = create_app()

