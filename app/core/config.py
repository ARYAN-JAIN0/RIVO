"""Configuration module for the RIVO application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from dotenv import load_dotenv

from app.core.exceptions import ConfigurationError

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    """Runtime configuration with validation."""

    APP_NAME: str
    APP_VERSION: str
    ENV: str
    DEBUG: bool
    DATABASE_URL: str
    LLM_API_KEY: str | None
    LLM_MODEL: str
    LLM_TEMPERATURE: float
    OLLAMA_URL: str
    OLLAMA_MODEL: str
    LLM_TIMEOUT_SECONDS: int
    LLM_MAX_RETRIES: int
    LLM_MIN_INTERVAL_SECONDS: float
    VECTOR_STORE_PATH: str
    SMTP_SERVER: str | None
    SMTP_PORT: int
    SMTP_USERNAME: str | None
    SMTP_PASSWORD: str | None
    JWT_SECRET: str
    JWT_ACCESS_TTL_MINUTES: int
    JWT_REFRESH_TTL_DAYS: int
    JWT_PERMISSIONS_VERSION: int
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    API_HOST: str
    API_PORT: int
    API_PREFIX: str
    LOG_LEVEL: str
    LOG_FILE: str

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


def _build_config(env: str | None = None) -> Config:
    resolved_env = (env or os.getenv("ENV", "development")).strip().lower()
    debug = _as_bool(os.getenv("DEBUG"), default=(resolved_env != "production"))

    config = Config(
        APP_NAME="RIVO",
        APP_VERSION=os.getenv("APP_VERSION", "1.0.0"),
        ENV=resolved_env,
        DEBUG=debug if resolved_env != "production" else False,
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///./rivo.db"),
        LLM_API_KEY=os.getenv("LLM_API_KEY"),
        LLM_MODEL=os.getenv("LLM_MODEL", "gpt-4"),
        LLM_TEMPERATURE=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        OLLAMA_URL=os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
        OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        LLM_TIMEOUT_SECONDS=int(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
        LLM_MAX_RETRIES=int(os.getenv("LLM_MAX_RETRIES", "2")),
        LLM_MIN_INTERVAL_SECONDS=float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "0.25")),
        VECTOR_STORE_PATH=os.getenv("VECTOR_STORE_PATH", "./chroma_db"),
        SMTP_SERVER=os.getenv("SMTP_SERVER"),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USERNAME=os.getenv("SMTP_USERNAME"),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD"),
        JWT_SECRET=os.getenv("JWT_SECRET", "change_me_jwt_secret"),
        JWT_ACCESS_TTL_MINUTES=int(os.getenv("JWT_ACCESS_TTL_MINUTES", "15")),
        JWT_REFRESH_TTL_DAYS=int(os.getenv("JWT_REFRESH_TTL_DAYS", "14")),
        JWT_PERMISSIONS_VERSION=int(os.getenv("JWT_PERMISSIONS_VERSION", "1")),
        REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        CELERY_BROKER_URL=os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
        CELERY_RESULT_BACKEND=os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
        API_HOST=os.getenv("API_HOST", "0.0.0.0"),
        API_PORT=int(os.getenv("API_PORT", "8000")),
        API_PREFIX=os.getenv("API_PREFIX", "/api/v1"),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO").upper(),
        LOG_FILE=os.getenv("LOG_FILE", "rivo.log"),
    )
    _validate_config(config)
    return config


def _validate_database_url(database_url: str) -> None:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"sqlite", "postgresql", "postgresql+psycopg2"}:
        raise ConfigurationError(
            "DATABASE_URL must use sqlite:// or postgresql:// style URL."
        )
    if parsed.scheme.startswith("postgresql") and not parsed.hostname:
        raise ConfigurationError("PostgreSQL DATABASE_URL is missing hostname.")


def _validate_config(config: Config) -> None:
    _validate_database_url(config.DATABASE_URL)

    if config.LLM_TIMEOUT_SECONDS < 1:
        raise ConfigurationError("LLM_TIMEOUT_SECONDS must be >= 1.")
    if config.LLM_MAX_RETRIES < 0:
        raise ConfigurationError("LLM_MAX_RETRIES must be >= 0.")
    if config.LLM_MIN_INTERVAL_SECONDS < 0:
        raise ConfigurationError("LLM_MIN_INTERVAL_SECONDS must be >= 0.")
    if config.JWT_ACCESS_TTL_MINUTES < 1:
        raise ConfigurationError("JWT_ACCESS_TTL_MINUTES must be >= 1.")
    if config.JWT_REFRESH_TTL_DAYS < 1:
        raise ConfigurationError("JWT_REFRESH_TTL_DAYS must be >= 1.")
    if config.LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigurationError("LOG_LEVEL must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL.")
    if config.is_production and "change_me" in config.DATABASE_URL.lower():
        raise ConfigurationError("Production DATABASE_URL uses placeholder credentials.")


@lru_cache(maxsize=8)
def get_config(env: str | None = None) -> Config:
    """Get validated configuration for the requested environment."""
    return _build_config(env)
