from app.database.models import Lead
from app.services.base_service import BaseService
from datetime import datetime

class LeadService(BaseService):

    def create_lead(self, data: dict):
        lead = Lead(**data)
        self.db.add(lead)
        self.commit()
        return lead

    def get_lead(self, lead_id: int):
        return self.db.query(Lead).filter(Lead.id == lead_id).first()

    def update_status(self, lead_id: int, status: str):
        lead = self.get_lead(lead_id)
        if not lead:
            return None
        lead.status = status
        lead.last_contacted = datetime.utcnow()
        self.commit()
        return lead

    def update_draft(self, lead_id: int, draft: str, confidence: int):
        lead = self.get_lead(lead_id)
        if not lead:
            return None
        lead.draft_message = draft
        lead.confidence_score = confidence
        self.commit()
        return lead
