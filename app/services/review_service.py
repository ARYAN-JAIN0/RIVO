"""Review workflow service facade for API requests."""

from __future__ import annotations

from app.database import db_handler


class ReviewService:
    """Service wrapper around existing human-review persistence functions."""

    def get_pending_reviews(self) -> list:
        return db_handler.fetch_pending_reviews()

    def mark_decision(
        self,
        lead_id: int,
        decision: str,
        edited_email: str | None = None,
        actor: str = "human",
    ) -> None:
        db_handler.mark_review_decision(
            lead_id=lead_id,
            decision=decision,
            edited_email=edited_email,
            actor=actor,
        )

