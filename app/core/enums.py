"""Enums for the RIVO application - FIXED VERSION

CRITICAL FIX: Status values now use title case to match actual application usage.
All agents, database handlers, and UI components use title case ("New", "Contacted", etc.),
so enums are updated to match this convention for consistency.
"""

from enum import Enum


class AgentType(Enum):
    """Types of agents in the system."""
    
    SDR = "sdr"
    SALES = "sales"
    FINANCE = "finance"
    NEGOTIATION = "negotiation"


class LeadStatus(Enum):
    """
    Status of leads in the pipeline.
    
    FIXED: Changed from lowercase to title case to match application usage.
    """
    
    NEW = "New"  # Changed from "new"
    CONTACTED = "Contacted"  # Changed from "contacted"
    QUALIFIED = "Qualified"  # Changed from "qualified"
    DISQUALIFIED = "Disqualified"  # Changed from "disqualified"


class DealStage(Enum):
    """
    Stage of deals in the sales pipeline.
    
    FIXED: Renamed from DealStatus to DealStage for clarity.
    Uses title case for consistency.
    """
    
    QUALIFIED = "Qualified"
    PROPOSAL_SENT = "Proposal Sent"
    WON = "Won"
    LOST = "Lost"


class ContractStatus(Enum):
    """
    Status of contracts.
    
    FIXED: Uses title case for consistency.
    """
    
    NEGOTIATING = "Negotiating"
    SIGNED = "Signed"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class InvoiceStatus(Enum):
    """
    Status of invoices.
    
    FIXED: Uses title case for consistency.
    """
    
    SENT = "Sent"
    PAID = "Paid"
    OVERDUE = "Overdue"


class ReviewStatus(Enum):
    """
    Status of human review for AI-generated content.
    
    NEW: Added enum for review workflows.
    """
    
    NEW = "New"
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    AUTO_APPROVED = "Auto-Approved"
    STRUCTURAL_FAILED = "STRUCTURAL_FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


# Convenience accessors for common status values
LEAD_NEW = LeadStatus.NEW.value
LEAD_CONTACTED = LeadStatus.CONTACTED.value
LEAD_QUALIFIED = LeadStatus.QUALIFIED.value

DEAL_QUALIFIED = DealStage.QUALIFIED.value
DEAL_PROPOSAL_SENT = DealStage.PROPOSAL_SENT.value

CONTRACT_NEGOTIATING = ContractStatus.NEGOTIATING.value
CONTRACT_SIGNED = ContractStatus.SIGNED.value

INVOICE_SENT = InvoiceStatus.SENT.value
INVOICE_OVERDUE = InvoiceStatus.OVERDUE.value
INVOICE_PAID = InvoiceStatus.PAID.value

REVIEW_PENDING = ReviewStatus.PENDING.value
REVIEW_APPROVED = ReviewStatus.APPROVED.value
