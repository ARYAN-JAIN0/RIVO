"""Contract service for contract workflow operations."""

from __future__ import annotations

from app.core.enums import ContractStatus
from app.database.models import Contract
from app.services.base_service import BaseService


class ContractService(BaseService):
    """Service for managing contracts with explicit validation."""

    def validate(self) -> None:
        if self.db is None:
            raise ValueError("Database session is not initialized.")

    def get_contract(self, contract_id: int) -> Contract | None:
        self.validate()
        return self.db.query(Contract).filter(Contract.id == contract_id).first()

    def mark_signed(self, contract_id: int) -> bool:
        self.validate()
        contract = self.get_contract(contract_id)
        if contract is None:
            return False
        contract.status = ContractStatus.SIGNED.value
        self.commit()
        return True

