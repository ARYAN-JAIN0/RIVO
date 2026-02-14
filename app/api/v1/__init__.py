from app.api.v1.endpoints import router

__all__ = ["router"]
"""Version 1 API package."""

from app.api.v1.router import api_router, get_api_router

__all__ = ["api_router", "get_api_router"]
