"""In-memory caching layer for LLM responses."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# In-memory cache store
_cache_store: dict[str, dict[str, Any]] = {}

# Default TTL in seconds (1 hour)
DEFAULT_TTL = 3600


def get_cache_key(data: str | dict[str, Any]) -> str:
    """Generate a cache key from input data.
    
    Args:
        data: String or dictionary to generate key from
        
    Returns:
        MD5 hash as cache key
    """
    if isinstance(data, dict):
        # Sort keys for consistent hashing
        data_str = str(sorted(data.items()))
    else:
        data_str = str(data)
    
    return hashlib.md5(data_str.encode()).hexdigest()


def get_from_cache(key: str) -> Any | None:
    """Get value from cache if exists and not expired.
    
    Args:
        key: Cache key
        
    Returns:
        Cached value or None if not found/expired
    """
    if key not in _cache_store:
        return None
    
    entry = _cache_store[key]
    expires_at = entry.get("expires_at", 0)
    
    if time.time() > expires_at:
        # Entry expired, remove it
        del _cache_store[key]
        logger.debug(
            "cache.expired",
            extra={"event": "cache.expired", "key": key[:8]},
        )
        return None
    
    logger.debug(
        "cache.hit",
        extra={"event": "cache.hit", "key": key[:8]},
    )
    return entry.get("value")


def set_cache(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """Set value in cache with TTL.
    
    Args:
        key: Cache key
        value: Value to cache
        ttl: Time to live in seconds
    """
    _cache_store[key] = {
        "value": value,
        "expires_at": time.time() + ttl,
        "created_at": time.time(),
    }
    logger.debug(
        "cache.set",
        extra={"event": "cache.set", "key": key[:8], "ttl": ttl},
    )


def clear_cache() -> None:
    """Clear all cache entries."""
    global _cache_store
    _cache_store = {}
    logger.info("cache.cleared", extra={"event": "cache.cleared"})


def clear_expired() -> int:
    """Clear expired cache entries.
    
    Returns:
        Number of entries cleared
    """
    now = time.time()
    expired_keys = [
        key for key, entry in _cache_store.items()
        if now > entry.get("expires_at", 0)
    ]
    
    for key in expired_keys:
        del _cache_store[key]
    
    if expired_keys:
        logger.info(
            "cache.expired_cleared",
            extra={"event": "cache.expired_cleared", "count": len(expired_keys)},
        )
    
    return len(expired_keys)


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics.
    
    Returns:
        Dictionary with cache stats
    """
    now = time.time()
    expired_count = sum(
        1 for entry in _cache_store.values()
        if now > entry.get("expires_at", 0)
    )
    
    return {
        "total_entries": len(_cache_store),
        "expired_entries": expired_count,
        "active_entries": len(_cache_store) - expired_count,
    }


# Cached LLM response wrapper
def cached_llm_call(
    prompt: str,
    llm_generate_func: callable,
    ttl: int = DEFAULT_TTL,
) -> str:
    """Execute LLM call with caching.
    
    Args:
        prompt: Prompt to send to LLM
        llm_generate_func: Function to call for generation
        ttl: Cache TTL in seconds
        
    Returns:
        LLM response (cached or fresh)
    """
    key = get_cache_key(prompt)
    
    # Try cache first
    cached = get_from_cache(key)
    if cached is not None:
        return cached
    
    # Generate fresh response
    response = llm_generate_func(prompt)
    
    # Cache successful responses
    if response:
        set_cache(key, response, ttl)
    
    return response
