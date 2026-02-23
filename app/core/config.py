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


def _strip_ollama_suffix(url: str) -> str:
    normalized = url.rstrip("/")
    lowered = normalized.lower()
    for suffix in ("/api/generate", "/api/embeddings", "/api/tags"):
        if lowered.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _resolve_ollama_urls() -> tuple[str, str, str]:
    raw_base = os.getenv("OLLAMA_URL")
    generate_url = os.getenv("OLLAMA_GENERATE_URL")
    embedding_url = os.getenv("OLLAMA_EMBEDDING_URL")

    if raw_base:
        base = _strip_ollama_suffix(raw_base)
    elif generate_url:
        base = _strip_ollama_suffix(generate_url)
    elif embedding_url:
        base = _strip_ollama_suffix(embedding_url)
    else:
        base = "http://localhost:11434"

    if not generate_url:
        generate_url = f"{base}/api/generate"
    if not embedding_url:
        embedding_url = f"{base}/api/embeddings"

    return base, generate_url.rstrip("/"), embedding_url.rstrip("/")


@dataclass(frozen=True)
class Config:
    """Runtime configuration with validation."""

    APP_NAME: str
    APP_VERSION: str
    ENV: str
    DEBUG: bool
    DATABASE_URL: str
    DB_CONNECTIVITY_REQUIRED: bool
    LLM_API_KEY: str | None
    LLM_MODEL: str
    LLM_TEMPERATURE: float
    # Backward-compatible base URL retained for legacy callsites.
    OLLAMA_URL: str
    OLLAMA_GENERATE_URL: str
    OLLAMA_EMBEDDING_URL: str
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
    # Automated Pipeline Configuration
    AUTO_PIPELINE_ENABLED: bool
    AUTO_PIPELINE_INTERVAL_HOURS: int
    AUTO_PIPELINE_TENANT_ID: int
    # Lead Scraper Configuration
    AUTO_LEAD_SCRAPE_INTERVAL_HOURS: int
    SCRAPER_RPS: float
    SCRAPER_BURST: int
    SCRAPER_DAILY_CAP: int
    # Security Configuration
    PASSWORD_PEPPER: str

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


def _build_config(env: str | None = None) -> Config:
    resolved_env = (env or os.getenv("ENV", "development")).strip().lower()
    debug = _as_bool(os.getenv("DEBUG"), default=(resolved_env != "production"))
    ollama_base_url, ollama_generate_url, ollama_embedding_url = _resolve_ollama_urls()

    config = Config(
        APP_NAME="RIVO",
        APP_VERSION=os.getenv("APP_VERSION", "1.0.0"),
        ENV=resolved_env,
        DEBUG=debug if resolved_env != "production" else False,
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///./rivo.db"),
        DB_CONNECTIVITY_REQUIRED=_as_bool(
            os.getenv("DB_CONNECTIVITY_REQUIRED"),
            default=(resolved_env == "production"),
        ),
        LLM_API_KEY=os.getenv("LLM_API_KEY"),
        LLM_MODEL=os.getenv("LLM_MODEL", "gpt-4"),
        LLM_TEMPERATURE=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        OLLAMA_URL=ollama_base_url,
        OLLAMA_GENERATE_URL=ollama_generate_url,
        OLLAMA_EMBEDDING_URL=ollama_embedding_url,
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
        # Automated Pipeline Configuration
        AUTO_PIPELINE_ENABLED=_as_bool(os.getenv("AUTO_PIPELINE_ENABLED"), default=False),
        AUTO_PIPELINE_INTERVAL_HOURS=int(os.getenv("AUTO_PIPELINE_INTERVAL_HOURS", "6")),
        AUTO_PIPELINE_TENANT_ID=int(os.getenv("AUTO_PIPELINE_TENANT_ID", "1")),
        # Lead Scraper Configuration
        AUTO_LEAD_SCRAPE_INTERVAL_HOURS=int(os.getenv("AUTO_LEAD_SCRAPE_INTERVAL_HOURS", "1")),
        SCRAPER_RPS=float(os.getenv("SCRAPER_RPS", "2.0")),
        SCRAPER_BURST=int(os.getenv("SCRAPER_BURST", "10")),
        SCRAPER_DAILY_CAP=int(os.getenv("SCRAPER_DAILY_CAP", "100")),
        # Security Configuration
        PASSWORD_PEPPER=os.getenv("PASSWORD_PEPPER", ""),
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


def _validate_http_url(name: str, value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError(f"{name} must be a valid http(s) URL.")


def _validate_config(config: Config) -> None:
    _validate_database_url(config.DATABASE_URL)
    _validate_http_url("OLLAMA_GENERATE_URL", config.OLLAMA_GENERATE_URL)
    _validate_http_url("OLLAMA_EMBEDDING_URL", config.OLLAMA_EMBEDDING_URL)

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
    # Automated Pipeline validation
    if config.AUTO_PIPELINE_INTERVAL_HOURS < 1:
        raise ConfigurationError("AUTO_PIPELINE_INTERVAL_HOURS must be >= 1.")
    if config.AUTO_PIPELINE_INTERVAL_HOURS > 24:
        raise ConfigurationError("AUTO_PIPELINE_INTERVAL_HOURS must be <= 24.")
    if config.AUTO_PIPELINE_TENANT_ID < 1:
        raise ConfigurationError("AUTO_PIPELINE_TENANT_ID must be >= 1.")
    # Lead Scraper validation
    if config.AUTO_LEAD_SCRAPE_INTERVAL_HOURS < 1:
        raise ConfigurationError("AUTO_LEAD_SCRAPE_INTERVAL_HOURS must be >= 1.")
    if config.AUTO_LEAD_SCRAPE_INTERVAL_HOURS > 24:
        raise ConfigurationError("AUTO_LEAD_SCRAPE_INTERVAL_HOURS must be <= 24.")
    if config.SCRAPER_RPS <= 0:
        raise ConfigurationError("SCRAPER_RPS must be > 0.")
    if config.SCRAPER_BURST < 1:
        raise ConfigurationError("SCRAPER_BURST must be >= 1.")
    if config.SCRAPER_DAILY_CAP < 1:
        raise ConfigurationError("SCRAPER_DAILY_CAP must be >= 1.")


@lru_cache(maxsize=8)
def get_config(env: str | None = None) -> Config:
    """Get validated configuration for the requested environment."""
    return _build_config(env)
