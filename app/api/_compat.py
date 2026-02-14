"""Compatibility wrappers for FastAPI symbols during scaffold/runtime fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

try:  # pragma: no cover - exercised when FastAPI is installed.
    from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Response, status
    from fastapi.responses import RedirectResponse
except ModuleNotFoundError:  # pragma: no cover - local fallback path.
    class APIRouter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.routes: list[tuple[str, str, Callable]] = []
            self.prefix = str(kwargs.get("prefix", ""))

        def include_router(self, router: "APIRouter", prefix: str = "", *args: Any, **kwargs: Any) -> None:
            merged_prefix = f"{self.prefix}{prefix}".rstrip("/")
            for method, path, handler in getattr(router, "routes", []):
                full_path = f"{merged_prefix}{path}" if path.startswith("/") else f"{merged_prefix}/{path}"
                self.routes.append((method, full_path, handler))

        def _decorator(self, method: str, path: str) -> Callable:
            def inner(func: Callable) -> Callable:
                self.routes.append((method, path, func))
                return func

            return inner

        def get(self, path: str, *args: Any, **kwargs: Any) -> Callable:
            return self._decorator("GET", path)

        def post(self, path: str, *args: Any, **kwargs: Any) -> Callable:
            return self._decorator("POST", path)

        def patch(self, path: str, *args: Any, **kwargs: Any) -> Callable:
            return self._decorator("PATCH", path)

    class FastAPI(APIRouter):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.title = kwargs.get("title", "app")
            self.version = kwargs.get("version", "0.0.0")

    @dataclass
    class HTTPException(Exception):
        status_code: int
        detail: str

    @dataclass
    class Response:
        content: bytes | str | None = None
        media_type: str | None = None
        status_code: int = 200
        headers: dict[str, str] | None = None

    class RedirectResponse(Response):
        def __init__(self, url: str, status_code: int = 307):
            super().__init__(content=None, media_type=None, status_code=status_code, headers={"location": url})

    def Depends(call: Callable | None = None) -> Any:
        return call

    def Query(default: Any = None, *args: Any, **kwargs: Any) -> Any:
        return default

    def Header(default: Any = None, *args: Any, **kwargs: Any) -> Any:
        return default

    class status:
        HTTP_200_OK = 200
        HTTP_201_CREATED = 201
        HTTP_302_FOUND = 302
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_422_UNPROCESSABLE_ENTITY = 422
        HTTP_500_INTERNAL_SERVER_ERROR = 500
