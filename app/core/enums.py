"""Enums for the RIVO application."""

from enum import Enum


class AgentType(Enum):
    """Types of agents in the system."""
    
    SDR = "sdr"
    SALES = "sales"
    FINANCE = "finance"
    NEGOTIATION = "negotiation"


class LeadStatus(Enum):
    """Status of leads."""
    
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"


class DealStatus(Enum):
    """Status of deals."""
    
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WON = "won"
    LOST = "lost"


class ContractStatus(Enum):
    """Status of contracts."""
    
    DRAFT = "draft"
    SENT = "sent"
    SIGNED = "signed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvoiceStatus(Enum):
    """Status of invoices."""
    
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
