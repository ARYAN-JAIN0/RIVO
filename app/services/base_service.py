"""Shared service base with robust session lifecycle behavior."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.db import SessionLocal


class BaseService:
    """Base class for services that operate on a SQLAlchemy session."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db or SessionLocal()

    def commit(self) -> None:
        """Commit current transaction and rollback on failure."""
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def rollback(self) -> None:
        self.db.rollback()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "BaseService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rollback()
        self.close()
