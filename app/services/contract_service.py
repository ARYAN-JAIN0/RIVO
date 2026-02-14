"""Contract service for contract workflow operations."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import ContractStatus
from app.database.models import Contract
from app.services.base_service import BaseService


class ContractService(BaseService):
    """Service for contract CRUD and negotiation transitions."""

    def _utcnow_naive(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def create_contract(
        self,
        deal_id: int,
        lead_id: int,
        contract_terms: str,
        contract_value: int,
        status: str | None = None,
        review_status: str = "Pending",
    ) -> Contract:
        contract = Contract(
            deal_id=deal_id,
            lead_id=lead_id,
            status=status or ContractStatus.NEGOTIATING.value,
            contract_terms=contract_terms,
            contract_value=contract_value,
            review_status=review_status,
            last_updated=self._utcnow_naive(),
        )
        self.db.add(contract)
        self.commit()
        self.db.refresh(contract)
        return contract

    def get_contract(self, contract_id: int) -> Contract | None:
        return self.db.query(Contract).filter(Contract.id == contract_id).first()

    def list_by_status(self, status: str) -> list[Contract]:
        return self.db.query(Contract).filter(Contract.status == status).all()

    def update_status(self, contract_id: int, status: str) -> Contract | None:
        contract = self.get_contract(contract_id)
        if contract is None:
            return None

        contract.status = status
        contract.last_updated = self._utcnow_naive()
        if status == ContractStatus.SIGNED.value:
            contract.signed_date = self._utcnow_naive()
        self.commit()
        self.db.refresh(contract)
        return contract

    def mark_signed(self, contract_id: int) -> bool:
        return self.update_status(contract_id=contract_id, status=ContractStatus.SIGNED.value) is not None

    def update_negotiation(
        self,
        contract_id: int,
        objections: str | None = None,
        proposed_solutions: str | None = None,
        confidence_score: int | None = None,
    ) -> Contract | None:
        contract = self.get_contract(contract_id)
        if contract is None:
            return None

        if objections is not None:
            contract.objections = objections
        if proposed_solutions is not None:
            contract.proposed_solutions = proposed_solutions
        if confidence_score is not None:
            contract.negotiation_points = f"confidence={confidence_score}"
        contract.last_updated = self._utcnow_naive()
        self.commit()
        self.db.refresh(contract)
        return contract
