from __future__ import annotations

"""Application entrypoint for FastAPI and legacy CLI execution."""

import logging

from app.agents.sdr_agent import run_sdr_agent
from app.api._compat import FastAPI
from app.api.v1.router import api_router
from app.core.config import get_config
from app.core.startup import bootstrap
from app.middleware import CorrelationIDFilter, CorrelationIDMiddleware, RateLimitMiddleware

# Configure logging with correlation ID filter
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create configured ASGI application with middleware stack.
    
    The middleware stack is applied in reverse order (LIFO):
    1. RateLimitMiddleware - Protects API from abuse
    2. CorrelationIDMiddleware - Adds request tracing IDs
    
    This ensures correlation IDs are available in rate limit logs.
    """
    bootstrap()
    cfg = get_config()
    
    app = FastAPI(
        title=cfg.APP_NAME,
        version=cfg.APP_VERSION,
        docs_url="/docs" if cfg.DEBUG else None,  # Disable docs in production
        redoc_url="/redoc" if cfg.DEBUG else None,
    )
    
    # Add middleware (order matters - last added is first executed)
    # Rate limiting should happen after correlation ID is set
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CorrelationIDMiddleware)
    
    # Include API routes
    app.include_router(api_router)

    @app.get("/")
    def root() -> dict:
        """Root endpoint returning service info."""
        return {"service": cfg.APP_NAME, "version": cfg.APP_VERSION, "api_prefix": cfg.API_PREFIX}

    @app.get("/health")
    def health() -> dict:
        """Health check endpoint for load balancers and monitoring."""
        return {"status": "healthy", "service": cfg.APP_NAME, "version": cfg.APP_VERSION}

    return app


app = create_app()


if __name__ == "__main__":
    # Legacy compatibility path retained during migration window.
    run_sdr_agent()
