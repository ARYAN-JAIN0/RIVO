from __future__ import annotations

"""Celery application bootstrap."""

import os
import uuid
from types import SimpleNamespace

try:  # pragma: no cover - exercised when celery is installed.
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - local fallback path.
    class _Conf(dict):
        def __getattr__(self, item):
            return self.get(item)

        def __setattr__(self, key, value):
            self[key] = value

    class _TaskWrapper:
        def __init__(self, fn, bind: bool = False, name: str | None = None):
            self._fn = fn
            self.bind = bind
            self.name = name or getattr(fn, "__name__", "task")

        def run(self, *args, **kwargs):
            if self.bind:
                bound = SimpleNamespace(request=SimpleNamespace(id="local-run"))
                return self._fn(bound, *args, **kwargs)
            return self._fn(*args, **kwargs)

        def delay(self, *args, **kwargs):
            task_id = uuid.uuid4().hex
            if self.bind:
                bound = SimpleNamespace(request=SimpleNamespace(id=task_id))
                result = self._fn(bound, *args, **kwargs)
            else:
                result = self._fn(*args, **kwargs)
            return SimpleNamespace(id=task_id, result=result)

        def apply_async(self, args=None, kwargs=None):
            return self.delay(*(args or ()), **(kwargs or {}))

        def __call__(self, *args, **kwargs):
            return self.run(*args, **kwargs)

    class Celery:
        def __init__(self, *args, **kwargs) -> None:
            self.conf = _Conf()

        def task(self, *decorator_args, **decorator_kwargs):
            bind = bool(decorator_kwargs.get("bind", False))
            name = decorator_kwargs.get("name")

            def decorate(fn):
                return _TaskWrapper(fn, bind=bind, name=name)

            if decorator_args and callable(decorator_args[0]):
                return decorate(decorator_args[0])
            return decorate

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
