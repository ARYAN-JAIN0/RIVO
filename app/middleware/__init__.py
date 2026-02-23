"""Middleware package for RIVO API.

This package provides middleware components for the RIVO API:

- CorrelationIDMiddleware: Adds unique request IDs for distributed tracing
- RateLimitMiddleware: Protects API from abuse and DoS attacks

Usage:
    from app.middleware import CorrelationIDMiddleware, RateLimitMiddleware
    from app.middleware.correlation import get_correlation_id

    # Add middleware to FastAPI app
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # Get correlation ID in request handlers
    correlation_id = get_correlation_id()
"""

from app.middleware.correlation import (
    CORRELATION_ID_HEADER,
    CorrelationIDFilter,
    CorrelationIDMiddleware,
    correlation_id_var,
    generate_correlation_id,
    get_correlation_id,
    validate_correlation_id,
)
from app.middleware.rate_limit import (
    RATE_LIMIT_ADMIN,
    RATE_LIMIT_AUTH,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_TRACKING,
    InMemoryRateLimiter,
    RateLimitMiddleware,
    get_client_identifier,
    rate_limit,
)

__all__ = [
    # Correlation ID
    "CORRELATION_ID_HEADER",
    "CorrelationIDFilter",
    "CorrelationIDMiddleware",
    "correlation_id_var",
    "generate_correlation_id",
    "get_correlation_id",
    "validate_correlation_id",
    # Rate Limiting
    "RATE_LIMIT_ADMIN",
    "RATE_LIMIT_AUTH",
    "RATE_LIMIT_DEFAULT",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_TRACKING",
    "InMemoryRateLimiter",
    "RateLimitMiddleware",
    "get_client_identifier",
    "rate_limit",
]
