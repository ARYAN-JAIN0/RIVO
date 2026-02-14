from __future__ import annotations

import os

from celery import Celery

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", broker_url)

celery_app = Celery("rivo", broker=broker_url, backend=result_backend)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Local/dev convenience: run tasks synchronously when requested.
if os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() in {"1", "true", "yes", "on"}:
    celery_app.conf.task_always_eager = True
"""Celery application bootstrap with safe fallback when Celery is unavailable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core.config import get_config

QUEUE_NAMES = (
    "agents.sdr",
    "agents.sales",
    "agents.negotiation",
    "agents.finance",
    "agents.pipeline",
)


@dataclass
class _CeleryFallback:
    """Small compatibility object used when Celery is not installed."""

    available: bool = False

    def task(self, *args: Any, **kwargs: Any) -> Callable:
        def _decorator(func: Callable) -> Callable:
            return func

        return _decorator


def create_celery_app() -> Any:
    """Create Celery app if dependency exists; otherwise return fallback shim."""
    config = get_config()
    try:
        from celery import Celery
        from kombu import Queue
    except ModuleNotFoundError:
        return _CeleryFallback()

    app = Celery(
        "rivo",
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
    )
    app.conf.task_default_queue = "agents.pipeline"
    app.conf.task_queues = [Queue(name) for name in QUEUE_NAMES]
    app.conf.task_acks_late = True
    app.conf.worker_prefetch_multiplier = 1
    app.conf.task_serializer = "json"
    app.conf.result_serializer = "json"
    app.conf.accept_content = ["json"]
    return app


celery_app = create_celery_app()

