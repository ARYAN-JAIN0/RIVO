from __future__ import annotations

from datetime import date

from app.schemas.contracts import ContractCreateRequest
from app.schemas.deals import DealCreateRequest
from app.schemas.invoices import InvoiceCreateRequest


def test_deal_schema_accepts_minimum_payload():
    payload = DealCreateRequest(lead_id=1, acv=1000, qualification_score=70)
    assert payload.lead_id == 1
    assert payload.acv == 1000


def test_contract_schema_requires_terms():
    payload = ContractCreateRequest(deal_id=1, lead_id=1, contract_terms="Net 30", contract_value=9000)
    assert payload.contract_terms == "Net 30"


def test_invoice_schema_parses_due_date():
    payload = InvoiceCreateRequest(contract_id=1, lead_id=1, amount=3000, due_date=date(2026, 4, 1))
    assert payload.due_date.isoformat() == "2026-04-01"
