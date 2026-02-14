from __future__ import annotations

import logging
import threading
import time

import requests

from app.core.config import get_config

logger = logging.getLogger(__name__)
_RATE_LOCK = threading.Lock()
_LAST_REQUEST_TS = 0.0


def _apply_rate_limit(min_interval_seconds: float) -> None:
    global _LAST_REQUEST_TS
    if min_interval_seconds <= 0:
        return

    with _RATE_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_REQUEST_TS
        if elapsed < min_interval_seconds:
            time.sleep(min_interval_seconds - elapsed)
        _LAST_REQUEST_TS = time.monotonic()


def call_llm(prompt: str, json_mode: bool = False) -> str:
    config = get_config()
    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    last_error: Exception | None = None
    total_attempts = config.LLM_MAX_RETRIES + 1

    for attempt in range(1, total_attempts + 1):
        try:
            _apply_rate_limit(config.LLM_MIN_INTERVAL_SECONDS)
            response = requests.post(
                config.OLLAMA_URL,
                json=payload,
                timeout=(10, config.LLM_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            body = response.json()
            return body.get("response", "")
        except (requests.exceptions.RequestException, ValueError) as exc:
            last_error = exc
            logger.warning(
                "llm.call.failed",
                extra={
                    "event": "llm.call.failed",
                    "attempt": attempt,
                    "attempts_total": total_attempts,
                    "error": str(exc),
                },
            )
            if attempt < total_attempts:
                time.sleep(min(2 * attempt, 5))

    logger.error(
        "llm.call.unavailable",
        extra={
            "event": "llm.call.unavailable",
            "ollama_url": config.OLLAMA_URL,
            "model": config.OLLAMA_MODEL,
            "error": str(last_error) if last_error else "unknown",
        },
    )
    return ""

