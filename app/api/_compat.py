"""Compatibility wrappers for FastAPI symbols during scaffold phase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

try:  # pragma: no cover - exercised when FastAPI is installed.
    from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
except ModuleNotFoundError:  # pragma: no cover - local fallback path.
    class APIRouter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.routes: list[tuple[str, str]] = []

        def include_router(self, *args: Any, **kwargs: Any) -> None:
            return None

        def _decorator(self, method: str, path: str) -> Callable:
            self.routes.append((method, path))

            def inner(func: Callable) -> Callable:
                return func

            return inner

        def get(self, path: str, *args: Any, **kwargs: Any) -> Callable:
            return self._decorator("GET", path)

        def post(self, path: str, *args: Any, **kwargs: Any) -> Callable:
            return self._decorator("POST", path)

        def patch(self, path: str, *args: Any, **kwargs: Any) -> Callable:
            return self._decorator("PATCH", path)

    @dataclass
    class HTTPException(Exception):
        status_code: int
        detail: str

    def Depends(call: Callable | None = None) -> Any:
        return call

    def Query(default: Any = None, *args: Any, **kwargs: Any) -> Any:
        return default

    def Header(default: Any = None, *args: Any, **kwargs: Any) -> Any:
        return default

    class status:
        HTTP_200_OK = 200
        HTTP_201_CREATED = 201
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_422_UNPROCESSABLE_ENTITY = 422
        HTTP_500_INTERNAL_SERVER_ERROR = 500
