"""Correlation ID middleware for request tracing.

This module provides middleware that adds a unique correlation ID to each request,
enabling distributed tracing and log correlation across the application.

Security Features:
- Generates cryptographically secure random IDs
- Validates incoming correlation IDs to prevent injection
- Adds correlation ID to all log entries

Usage:
    from app.middleware.correlation import CorrelationIDMiddleware
    app.add_middleware(CorrelationIDMiddleware)
"""

from __future__ import annotations

import logging
import secrets
import string
from contextvars import ContextVar
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Context variable to store correlation ID for the current request
# This allows access to the correlation ID from anywhere in the request context
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Allowed characters for correlation ID (alphanumeric only for safety)
ALLOWED_CHARS = string.ascii_letters + string.digits
CORRELATION_ID_LENGTH = 16
CORRELATION_ID_HEADER = "X-Request-ID"


def generate_correlation_id() -> str:
    """Generate a cryptographically secure random correlation ID.
    
    Returns:
        A random alphanumeric string of length CORRELATION_ID_LENGTH.
    """
    return "".join(secrets.choice(ALLOWED_CHARS) for _ in range(CORRELATION_ID_LENGTH))


def validate_correlation_id(correlation_id: str) -> bool:
    """Validate that a correlation ID contains only safe characters.
    
    This prevents injection attacks through the correlation ID header.
    
    Args:
        correlation_id: The correlation ID to validate.
        
    Returns:
        True if the correlation ID is valid, False otherwise.
    """
    if not correlation_id:
        return False
    if len(correlation_id) > 64:  # Prevent excessively long IDs
        return False
    return all(c in ALLOWED_CHARS for c in correlation_id)


def get_correlation_id() -> str | None:
    """Get the correlation ID for the current request context.
    
    This function can be called from anywhere in the request handling
    code to get the current correlation ID for logging or other purposes.
    
    Returns:
        The correlation ID for the current request, or None if not in a request context.
    """
    return correlation_id_var.get()


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that adds a unique correlation ID to each request.
    
    This middleware:
    1. Checks for an existing correlation ID in the request headers
    2. Validates the incoming correlation ID for safety
    3. Generates a new correlation ID if none exists or if invalid
    4. Stores the correlation ID in a context variable for access anywhere
    5. Adds the correlation ID to the response headers
    6. Includes the correlation ID in log entries
    
    Attributes:
        app: The ASGI application to wrap.
        header_name: The name of the header to use for the correlation ID.
    """
    
    def __init__(self, app: ASGIApp, header_name: str = CORRELATION_ID_HEADER) -> None:
        """Initialize the correlation ID middleware.
        
        Args:
            app: The ASGI application to wrap.
            header_name: The name of the header to use for the correlation ID.
                         Defaults to "X-Request-ID".
        """
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add correlation ID.
        
        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler to call.
            
        Returns:
            The HTTP response with correlation ID header added.
        """
        # Try to get existing correlation ID from request headers
        incoming_id = request.headers.get(self.header_name)
        
        # Validate incoming ID or generate a new one
        if incoming_id and validate_correlation_id(incoming_id):
            correlation_id = incoming_id
        else:
            correlation_id = generate_correlation_id()
            if incoming_id:
                # Log if we rejected an incoming ID
                logger.warning(
                    "correlation_id.rejected",
                    extra={
                        "event": "correlation_id.rejected",
                        "reason": "invalid_characters",
                        "incoming_id_length": len(incoming_id) if incoming_id else 0,
                    },
                )
        
        # Store in context variable for access anywhere in the request
        correlation_id_var.set(correlation_id)
        
        # Add to request state for easy access in route handlers
        request.state.correlation_id = correlation_id
        
        # Log the request with correlation ID
        logger.info(
            "request.started",
            extra={
                "event": "request.started",
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": self._get_client_ip(request),
            },
        )
        
        # Process the request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers[self.header_name] = correlation_id
        
        # Log the response
        logger.info(
            "request.completed",
            extra={
                "event": "request.completed",
                "correlation_id": correlation_id,
                "status_code": response.status_code,
            },
        )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract the client IP address from the request.
        
        Handles X-Forwarded-For header for requests behind a proxy.
        
        Args:
            request: The HTTP request.
            
        Returns:
            The client IP address as a string.
        """
        # Check X-Forwarded-For header first (for requests behind a proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            return forwarded_for.split(",")[0].strip()
        
        # Fall back to direct client address
        if request.client:
            return request.client.host
        
        return "unknown"


class CorrelationIDFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records.
    
    Add this filter to your logging handlers to automatically include
    the correlation ID in all log entries within a request context.
    
    Usage:
        handler = logging.StreamHandler()
        handler.addFilter(CorrelationIDFilter())
        logger.addHandler(handler)
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record.
        
        Args:
            record: The log record to modify.
            
        Returns:
            Always returns True to allow the record to be logged.
        """
        record.correlation_id = get_correlation_id() or "no-correlation-id"
        return True
