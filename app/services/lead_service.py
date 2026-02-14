"""Lead service with migration-safe behavior for legacy schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.enums import LeadStatus
from app.database.models import Lead
from app.services.base_service import BaseService


class LeadService(BaseService):
    """Service for lead CRUD and status transitions.

    This service currently targets the legacy `app.database.models.Lead` model to
    preserve runtime compatibility while the modular model migration is in progress.
    """

    def create_lead(self, data: dict[str, Any]) -> Lead:
        payload = dict(data)
        lead = Lead(**payload)
        self.db.add(lead)
        self.commit()
        self.db.refresh(lead)
        return lead

    def get_lead(self, lead_id: int) -> Lead | None:
        return self.db.query(Lead).filter(Lead.id == lead_id).first()

    def list_by_status(self, status: str) -> list[Lead]:
        return self.db.query(Lead).filter(Lead.status == status).all()

    def update_status(self, lead_id: int, status: str) -> Lead | None:
        lead = self.get_lead(lead_id)
        if lead is None:
            return None

        lead.status = status
        if status == LeadStatus.CONTACTED.value:
            lead.last_contacted = datetime.now(timezone.utc).replace(tzinfo=None)
        self.commit()
        self.db.refresh(lead)
        return lead

    def update_draft(self, lead_id: int, draft: str, confidence: int) -> Lead | None:
        lead = self.get_lead(lead_id)
        if lead is None:
            return None

        lead.draft_message = draft
        lead.confidence_score = confidence
        self.commit()
        self.db.refresh(lead)
        return lead
