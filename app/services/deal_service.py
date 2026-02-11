class DealService(BaseService):

    def create_deal(self, lead_id: int, acv: int, qualification_score: int):
        deal = Deal(
            lead_id=lead_id,
            acv=acv,
            qualification_score=qualification_score,
            stage="Qualification",
            created_at=datetime.utcnow()
        )
        self.db.add(deal)
        self.commit()
        return deal

    def update_stage(self, deal_id: int, new_stage: str):
        deal = self.db.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            deal.stage = new_stage
            deal.last_updated = datetime.utcnow()
            self.commit()
        return deal
