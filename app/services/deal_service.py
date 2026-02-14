"""Deal service with migration-safe behavior for legacy schema."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import DealStage
from app.database.models import Deal
from app.services.base_service import BaseService


def _utcnow_naive() -> datetime:
    """Return UTC now as naive datetime for legacy columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DealService(BaseService):
    """Service for deal CRUD and stage transitions."""

    def create_deal(
        self,
        lead_id: int,
        acv: int,
        qualification_score: int,
        company: str | None = None,
        notes: str | None = None,
        stage: str | None = None,
        review_status: str = "Pending",
    ) -> Deal:
        deal = Deal(
            lead_id=lead_id,
            company=company,
            acv=acv,
            qualification_score=qualification_score,
            stage=stage or DealStage.QUALIFIED.value,
            notes=notes,
            review_status=review_status,
            created_at=_utcnow_naive(),
            last_updated=_utcnow_naive(),
        )
        self.db.add(deal)
        self.commit()
        self.db.refresh(deal)
        return deal

    def get_deal(self, deal_id: int) -> Deal | None:
        return self.db.query(Deal).filter(Deal.id == deal_id).first()

    def list_by_stage(self, stage: str) -> list[Deal]:
        return self.db.query(Deal).filter(Deal.stage == stage).all()

    def update_stage(self, deal_id: int, new_stage: str) -> Deal | None:
        deal = self.get_deal(deal_id)
        if deal is None:
            return None

        deal.stage = new_stage
        deal.last_updated = _utcnow_naive()
        self.commit()
        self.db.refresh(deal)
        return deal

    def update_notes(self, deal_id: int, notes: str) -> Deal | None:
        deal = self.get_deal(deal_id)
        if deal is None:
            return None

        deal.notes = notes
        deal.last_updated = _utcnow_naive()
        self.commit()
        self.db.refresh(deal)
        return deal
