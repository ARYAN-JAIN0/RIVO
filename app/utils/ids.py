"""Identifier generation helpers."""

from __future__ import annotations

import uuid


def new_run_id() -> str:
    """Create a UUID4-based run identifier."""
    return str(uuid.uuid4())

