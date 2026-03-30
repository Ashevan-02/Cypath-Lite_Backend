from __future__ import annotations

from celery import Celery

from app.core.config import settings


def _make_celery() -> Celery:
    celery = Celery(
        "cypath_lite",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    return celery


celery_app = _make_celery()

