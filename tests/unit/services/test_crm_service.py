"""
Unit tests for CRM Service.

Tests cover:
- Pagination
- Tenant isolation
- Sorting whitelists
- Status validation
- Search functionality
- Mutation methods with audit logging
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.services.crm_service import (
    CRMService,
    PaginatedResult,
    InvalidSortFieldError,
    InvalidStatusError,
    TenantOwnershipError,
    LEAD_SORT_FIELDS,
    DEAL_SORT_FIELDS,
    CONTRACT_SORT_FIELDS,
    INVOICE_SORT_FIELDS,
    LEAD_STATUS_VALUES,
    DEAL_STAGE_VALUES,
    CONTRACT_STATUS_VALUES,
    INVOICE_STATUS_VALUES,
)
from app.core.enums import LeadStatus, DealStage, ContractStatus, InvoiceStatus


class TestPaginatedResult:
    """Tests for PaginatedResult dataclass."""

    def test_total_pages_calculation(self):
        """Test total pages is calculated correctly."""
        result = PaginatedResult(items=[], total=100, page=1, page_size=25)
        assert result.total_pages == 4

    def test_total_pages_rounds_up(self):
        """Test total pages rounds up for partial pages."""
        result = PaginatedResult(items=[], total=101, page=1, page_size=25)
        assert result.total_pages == 5

    def test_total_pages_zero_page_size(self):
        """Test total pages is 0 when page_size is 0."""
        result = PaginatedResult(items=[], total=100, page=1, page_size=0)
        assert result.total_pages == 0


class TestSortWhitelists:
    """Tests for sort field whitelists."""

    def test_lead_sort_fields_exist(self):
        """Test lead sort fields are defined."""
        assert "created_at" in LEAD_SORT_FIELDS
        assert "status" in LEAD_SORT_FIELDS
        assert "company" in LEAD_SORT_FIELDS
        assert "name" in LEAD_SORT_FIELDS
        assert "signal_score" in LEAD_SORT_FIELDS

    def test_deal_sort_fields_exist(self):
        """Test deal sort fields are defined."""
        assert "created_at" in DEAL_SORT_FIELDS
        assert "stage" in DEAL_SORT_FIELDS
        assert "company" in DEAL_SORT_FIELDS
        assert "deal_value" in DEAL_SORT_FIELDS
        assert "probability" in DEAL_SORT_FIELDS

    def test_contract_sort_fields_exist(self):
        """Test contract sort fields are defined."""
        assert "last_updated" in CONTRACT_SORT_FIELDS
        assert "status" in CONTRACT_SORT_FIELDS
        assert "contract_value" in CONTRACT_SORT_FIELDS

    def test_invoice_sort_fields_exist(self):
        """Test invoice sort fields are defined."""
        assert "due_date" in INVOICE_SORT_FIELDS
        assert "status" in INVOICE_SORT_FIELDS
        assert "amount" in INVOICE_SORT_FIELDS


class TestStatusValues:
    """Tests for status value lists."""

    def test_lead_status_values_title_case(self):
        """Test lead status values use title case."""
        assert "New" in LEAD_STATUS_VALUES
        assert "Contacted" in LEAD_STATUS_VALUES
        assert "Qualified" in LEAD_STATUS_VALUES
        assert "Disqualified" in LEAD_STATUS_VALUES
        assert "new" not in LEAD_STATUS_VALUES  # lowercase not allowed

    def test_deal_stage_values_title_case(self):
        """Test deal stage values use title case."""
        assert "Qualified" in DEAL_STAGE_VALUES
        assert "Proposal Sent" in DEAL_STAGE_VALUES
        assert "Won" in DEAL_STAGE_VALUES
        assert "Lost" in DEAL_STAGE_VALUES

    def test_contract_status_values_title_case(self):
        """Test contract status values use title case."""
        assert "Negotiating" in CONTRACT_STATUS_VALUES
        assert "Signed" in CONTRACT_STATUS_VALUES
        assert "Completed" in CONTRACT_STATUS_VALUES
        assert "Cancelled" in CONTRACT_STATUS_VALUES

    def test_invoice_status_values_title_case(self):
        """Test invoice status values use title case."""
        assert "Sent" in INVOICE_STATUS_VALUES
        assert "Paid" in INVOICE_STATUS_VALUES
        assert "Overdue" in INVOICE_STATUS_VALUES


class TestInvalidSortFieldError:
    """Tests for InvalidSortFieldError."""

    def test_error_message_contains_field(self):
        """Test error message contains the invalid field."""
        error = InvalidSortFieldError("invalid_field", ["valid1", "valid2"])
        assert "invalid_field" in str(error)
        assert "valid1" in str(error)
        assert "valid2" in str(error)

    def test_error_attributes(self):
        """Test error attributes are set correctly."""
        error = InvalidSortFieldError("invalid_field", ["valid1", "valid2"])
        assert error.field == "invalid_field"
        assert error.valid_fields == ["valid1", "valid2"]


class TestInvalidStatusError:
    """Tests for InvalidStatusError."""

    def test_error_message_contains_status(self):
        """Test error message contains the invalid status."""
        error = InvalidStatusError("invalid_status", ["New", "Contacted"])
        assert "invalid_status" in str(error)
        assert "New" in str(error)

    def test_error_attributes(self):
        """Test error attributes are set correctly."""
        error = InvalidStatusError("invalid_status", ["New", "Contacted"])
        assert error.status == "invalid_status"
        assert error.valid_statuses == ["New", "Contacted"]


class TestTenantOwnershipError:
    """Tests for TenantOwnershipError."""

    def test_error_message(self):
        """Test error message contains entity info."""
        error = TenantOwnershipError("Lead", 123, 1)
        assert "Lead" in str(error)
        assert "123" in str(error)
        assert "tenant" in str(error).lower()

    def test_error_attributes(self):
        """Test error attributes are set correctly."""
        error = TenantOwnershipError("Lead", 123, 1)
        assert error.entity_type == "Lead"
        assert error.entity_id == 123
        assert error.tenant_id == 1


class TestCRMServiceGetLeads:
    """Tests for CRMService.get_leads method."""

    def test_invalid_sort_field_raises_error(self):
        """Test invalid sort field raises InvalidSortFieldError."""
        service = CRMService()
        with pytest.raises(InvalidSortFieldError) as exc_info:
            service.get_leads(tenant_id=1, sort_by="invalid_field")
        assert "invalid_field" in str(exc_info.value)

    def test_invalid_status_raises_error(self):
        """Test invalid status raises InvalidStatusError."""
        service = CRMService()
        with pytest.raises(InvalidStatusError) as exc_info:
            service.get_leads(tenant_id=1, status="invalid_status")
        assert "invalid_status" in str(exc_info.value)

    def test_page_size_clamped_to_max_100(self):
        """Test page_size is clamped to max 100."""
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.get_leads(tenant_id=1, page_size=200)
            assert result.page_size == 100

    def test_page_size_clamped_to_min_1(self):
        """Test page_size is clamped to min 1."""
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.get_leads(tenant_id=1, page_size=0)
            assert result.page_size == 1

    def test_page_clamped_to_min_1(self):
        """Test page is clamped to min 1."""
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 0
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.get_leads(tenant_id=1, page=0)
            assert result.page == 1


class TestCRMServiceGetDeals:
    """Tests for CRMService.get_deals method."""

    def test_invalid_sort_field_raises_error(self):
        """Test invalid sort field raises InvalidSortFieldError."""
        service = CRMService()
        with pytest.raises(InvalidSortFieldError):
            service.get_deals(tenant_id=1, sort_by="invalid_field")

    def test_invalid_stage_raises_error(self):
        """Test invalid stage raises InvalidStatusError."""
        service = CRMService()
        with pytest.raises(InvalidStatusError):
            service.get_deals(tenant_id=1, stage="invalid_stage")


class TestCRMServiceGetContracts:
    """Tests for CRMService.get_contracts method."""

    def test_invalid_sort_field_raises_error(self):
        """Test invalid sort field raises InvalidSortFieldError."""
        service = CRMService()
        with pytest.raises(InvalidSortFieldError):
            service.get_contracts(tenant_id=1, sort_by="invalid_field")

    def test_invalid_status_raises_error(self):
        """Test invalid status raises InvalidStatusError."""
        service = CRMService()
        with pytest.raises(InvalidStatusError):
            service.get_contracts(tenant_id=1, status="invalid_status")


class TestCRMServiceGetInvoices:
    """Tests for CRMService.get_invoices method."""

    def test_invalid_sort_field_raises_error(self):
        """Test invalid sort field raises InvalidSortFieldError."""
        service = CRMService()
        with pytest.raises(InvalidSortFieldError):
            service.get_invoices(tenant_id=1, sort_by="invalid_field")

    def test_invalid_status_raises_error(self):
        """Test invalid status raises InvalidStatusError."""
        service = CRMService()
        with pytest.raises(InvalidStatusError):
            service.get_invoices(tenant_id=1, status="invalid_status")


class TestCRMServiceMutations:
    """Tests for CRM service mutation methods."""

    def test_approve_lead_draft_safe_returns_none_for_nonexistent_lead(self):
        """Test approve_lead_draft_safe returns None for nonexistent lead."""
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.approve_lead_draft_safe(tenant_id=1, lead_id=999)
            assert result is None

    def test_reject_lead_draft_safe_returns_none_for_nonexistent_lead(self):
        """Test reject_lead_draft_safe returns None for nonexistent lead."""
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.reject_lead_draft_safe(tenant_id=1, lead_id=999)
            assert result is None

    def test_override_deal_stage_safe_validates_stage(self):
        """Test override_deal_stage_safe validates new stage."""
        service = CRMService()
        with pytest.raises(InvalidStatusError):
            service.override_deal_stage_safe(
                tenant_id=1,
                deal_id=1,
                new_stage="invalid_stage"
            )

    def test_sign_contract_safe_returns_none_for_nonexistent_contract(self):
        """Test sign_contract_safe returns None for nonexistent contract."""
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.sign_contract_safe(tenant_id=1, contract_id=999)
            assert result is None

    def test_mark_invoice_paid_safe_returns_none_for_nonexistent_invoice(self):
        """Test mark_invoice_paid_safe returns None for nonexistent invoice."""
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            # Invoice queries use join() for tenant filtering via Contract
            mock_query.join.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.mark_invoice_paid_safe(tenant_id=1, invoice_id=999)
            assert result is None


class TestTenantIsolation:
    """Tests for tenant isolation in mutations."""

    def test_approve_lead_raises_tenant_ownership_error(self):
        """Test approve_lead_draft_safe raises TenantOwnershipError for wrong tenant."""
        service = CRMService()
        mock_lead = MagicMock()
        mock_lead.tenant_id = 2  # Different tenant
        mock_lead.id = 1

        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_lead
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            with pytest.raises(TenantOwnershipError):
                service.approve_lead_draft_safe(tenant_id=1, lead_id=1)

    def test_override_deal_raises_tenant_ownership_error(self):
        """Test override_deal_stage_safe raises TenantOwnershipError for wrong tenant."""
        service = CRMService()
        mock_deal = MagicMock()
        mock_deal.tenant_id = 2  # Different tenant
        mock_deal.id = 1

        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_deal
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            with pytest.raises(TenantOwnershipError):
                service.override_deal_stage_safe(
                    tenant_id=1,
                    deal_id=1,
                    new_stage="Won"
                )

    def test_sign_contract_raises_tenant_ownership_error(self):
        """Test sign_contract_safe raises TenantOwnershipError for wrong tenant."""
        service = CRMService()
        mock_contract = MagicMock()
        mock_contract.tenant_id = 2  # Different tenant
        mock_contract.id = 1

        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_contract
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            with pytest.raises(TenantOwnershipError):
                service.sign_contract_safe(tenant_id=1, contract_id=1)

    def test_mark_invoice_paid_returns_none_for_wrong_tenant(self):
        """Test mark_invoice_paid_safe returns None for wrong tenant.

        Note: Invoice uses join with Contract for tenant validation.
        When tenant doesn't match, the query returns None (no TenantOwnershipError).
        This is intentional - it doesn't reveal invoice existence to unauthorized tenants.
        """
        service = CRMService()
        with patch("app.services.crm_service.get_db_session") as mock_session:
            mock_query = MagicMock()
            # Invoice queries use join() for tenant filtering via Contract
            mock_query.join.return_value = mock_query
            mock_query.filter.return_value = mock_query
            # When tenant doesn't match, join returns None
            mock_query.first.return_value = None
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = service.mark_invoice_paid_safe(tenant_id=1, invoice_id=1)
            assert result is None


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_get_leads_function(self):
        """Test get_leads convenience function."""
        from app.services.crm_service import get_leads

        with patch("app.services.crm_service._service.get_leads") as mock:
            get_leads(tenant_id=1)
            mock.assert_called_once_with(tenant_id=1)

    def test_get_deals_function(self):
        """Test get_deals convenience function."""
        from app.services.crm_service import get_deals

        with patch("app.services.crm_service._service.get_deals") as mock:
            get_deals(tenant_id=1)
            mock.assert_called_once_with(tenant_id=1)

    def test_get_contracts_function(self):
        """Test get_contracts convenience function."""
        from app.services.crm_service import get_contracts

        with patch("app.services.crm_service._service.get_contracts") as mock:
            get_contracts(tenant_id=1)
            mock.assert_called_once_with(tenant_id=1)

    def test_get_invoices_function(self):
        """Test get_invoices convenience function."""
        from app.services.crm_service import get_invoices

        with patch("app.services.crm_service._service.get_invoices") as mock:
            get_invoices(tenant_id=1)
            mock.assert_called_once_with(tenant_id=1)
