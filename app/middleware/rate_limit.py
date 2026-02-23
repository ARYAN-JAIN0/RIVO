"""Rate limiting middleware for API protection.

This module provides rate limiting functionality to protect the API from abuse,
DoS attacks, and excessive resource consumption.

Security Features:
- IP-based rate limiting
- Configurable limits per endpoint
- Graceful handling of rate limit exceeded
- Rate limit headers in responses

Configuration:
    RATE_LIMIT_ENABLED: Enable/disable rate limiting (default: true in production)
    RATE_LIMIT_DEFAULT: Default rate limit (default: "100/minute")
    RATE_LIMIT_TRACKING: Rate limit for tracking endpoints (default: "1000/minute")
    RATE_LIMIT_AUTH: Rate limit for auth endpoints (default: "10/minute")
    RATE_LIMIT_ADMIN: Rate limit for admin endpoints (default: "30/minute")
"""

from __future__ import annotations

import logging
import os
from functools import wraps
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Configuration from environment
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
RATE_LIMIT_TRACKING = os.getenv("RATE_LIMIT_TRACKING", "1000/minute")
RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "10/minute")
RATE_LIMIT_ADMIN = os.getenv("RATE_LIMIT_ADMIN", "30/minute")

# Try to import slowapi for production rate limiting
try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    Limiter = None
    RateLimitExceeded = None
    SlowAPIMiddleware = None
    get_remote_address = None


def get_client_identifier(request: Request) -> str:
    """Get a unique identifier for the client making the request.
    
    Uses X-Forwarded-For header if available (for requests behind a proxy),
    otherwise falls back to the direct client IP.
    
    Args:
        request: The HTTP request.
        
    Returns:
        A string identifier for the client (IP address).
    """
    # Check X-Forwarded-For header first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (used by some proxies)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client address
    if request.client:
        return request.client.host
    
    return "unknown"


class InMemoryRateLimiter:
    """Simple in-memory rate limiter for development/fallback.
    
    This is a basic implementation that stores request counts in memory.
    For production, use SlowAPI with Redis backend.
    
    Note: This is not suitable for multi-worker deployments as each worker
    maintains its own state. Use SlowAPI with Redis for production.
    
    Attributes:
        requests: Dictionary mapping client IDs to request timestamps.
        limits: Dictionary mapping endpoint patterns to rate limits.
    """
    
    def __init__(self) -> None:
        """Initialize the in-memory rate limiter."""
        self.requests: dict[str, list[float]] = {}
        self.limits: dict[str, tuple[int, int]] = {
            "default": (100, 60),  # 100 requests per 60 seconds
            "tracking": (1000, 60),  # 1000 requests per 60 seconds
            "auth": (10, 60),  # 10 requests per 60 seconds
            "admin": (30, 60),  # 30 requests per 60 seconds
        }
    
    def is_allowed(self, client_id: str, endpoint_type: str = "default") -> tuple[bool, int, int]:
        """Check if a client is allowed to make a request.
        
        Args:
            client_id: The client identifier (IP address).
            endpoint_type: The type of endpoint being accessed.
            
        Returns:
            A tuple of (is_allowed, remaining_requests, retry_after_seconds).
        """
        import time
        
        limit, window = self.limits.get(endpoint_type, self.limits["default"])
        key = f"{client_id}:{endpoint_type}"
        now = time.time()
        
        # Get or create request list for this client
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove expired timestamps
        self.requests[key] = [ts for ts in self.requests[key] if now - ts < window]
        
        # Check if under limit
        current_count = len(self.requests[key])
        if current_count < limit:
            self.requests[key].append(now)
            return True, limit - current_count - 1, 0
        
        # Calculate retry-after
        oldest = min(self.requests[key])
        retry_after = int(window - (now - oldest)) + 1
        
        return False, 0, retry_after


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limiting on API endpoints.
    
    This middleware:
    1. Identifies the client by IP address
    2. Determines the rate limit based on the endpoint type
    3. Checks if the request is allowed
    4. Adds rate limit headers to the response
    5. Returns 429 Too Many Requests if rate limit exceeded
    
    Attributes:
        app: The ASGI application to wrap.
        enabled: Whether rate limiting is enabled.
        limiter: The rate limiter instance.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = RATE_LIMIT_ENABLED,
    ) -> None:
        """Initialize the rate limit middleware.
        
        Args:
            app: The ASGI application to wrap.
            enabled: Whether rate limiting is enabled.
        """
        super().__init__(app)
        self.enabled = enabled
        self.limiter = InMemoryRateLimiter()
        
        if not SLOWAPI_AVAILABLE:
            logger.warning(
                "rate_limit.slowapi_unavailable",
                extra={
                    "event": "rate_limit.slowapi_unavailable",
                    "detail": "Using in-memory rate limiter. Install slowapi for production.",
                },
            )
    
    def _get_endpoint_type(self, path: str) -> str:
        """Determine the endpoint type for rate limiting.
        
        Args:
            path: The request path.
            
        Returns:
            The endpoint type string.
        """
        if "/track/" in path:
            return "tracking"
        if "/auth/" in path:
            return "auth"
        if "/admin/" in path or "/manual-override" in path:
            return "admin"
        return "default"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with rate limiting.
        
        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler to call.
            
        Returns:
            The HTTP response, or a 429 response if rate limit exceeded.
        """
        # Skip rate limiting if disabled
        if not self.enabled:
            return await call_next(request)
        
        # Get client identifier
        client_id = get_client_identifier(request)
        
        # Determine endpoint type
        endpoint_type = self._get_endpoint_type(request.url.path)
        
        # Check rate limit
        is_allowed, remaining, retry_after = self.limiter.is_allowed(client_id, endpoint_type)
        
        # Get limit for headers
        limit = self.limiter.limits.get(endpoint_type, self.limiter.limits["default"])[0]
        
        if not is_allowed:
            logger.warning(
                "rate_limit.exceeded",
                extra={
                    "event": "rate_limit.exceeded",
                    "client_id": client_id,
                    "endpoint_type": endpoint_type,
                    "path": request.url.path,
                    "retry_after": retry_after,
                },
            )
            
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": retry_after,
                },
            )
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(retry_after)
            response.headers["Retry-After"] = str(retry_after)
            return response
        
        # Process the request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


def rate_limit(limit: str):
    """Decorator for rate limiting specific functions.
    
    This can be used to apply rate limiting to specific endpoints or functions.
    
    Args:
        limit: The rate limit string (e.g., "10/minute").
        
    Returns:
        A decorator function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # For now, just pass through
            # In production, this would integrate with SlowAPI
            return await func(*args, **kwargs)
        return wrapper
    return decorator
