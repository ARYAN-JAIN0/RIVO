"""Feature engineering utilities for LLM inputs."""

from __future__ import annotations

from typing import Any


def extract_features(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Extract structured features from raw data for LLM consumption.
    
    This reduces prompt size and focuses the LLM on relevant features
    rather than raw unstructured data.
    
    Args:
        raw_data: Raw data dictionary (e.g., lead data, deal data)
        
    Returns:
        Dictionary of extracted features
    """
    features = {}
    
    # Common fields extraction
    if "deal_size" in raw_data:
        features["deal_size"] = raw_data.get("deal_size")
    
    if "avg_delay" in raw_data:
        features["avg_delay"] = raw_data.get("avg_delay")
    
    if "risk_score" in raw_data:
        features["risk_score"] = raw_data.get("risk_score")
    
    # Lead-specific features
    if "company_size" in raw_data:
        features["company_size"] = raw_data.get("company_size")
    
    if "industry" in raw_data:
        features["industry"] = raw_data.get("industry")
    
    if "role" in raw_data:
        features["role"] = raw_data.get("role")
    
    if "signal_score" in raw_data:
        features["signal_score"] = raw_data.get("signal_score")
    
    # Contract/invoice features
    if "amount_due" in raw_data:
        features["amount_due"] = raw_data.get("amount_due")
    
    if "days_overdue" in raw_data:
        features["days_overdue"] = raw_data.get("days_overdue")
    
    if "payment_history" in raw_data:
        features["payment_history"] = raw_data.get("payment_history")
    
    return features


def extract_lead_features(lead_data: dict[str, Any]) -> dict[str, Any]:
    """Extract features specifically for lead processing.
    
    Args:
        lead_data: Raw lead data dictionary
        
    Returns:
        Extracted lead features
    """
    return {
        "company_size": lead_data.get("company_size"),
        "industry": lead_data.get("industry"),
        "role": lead_data.get("role"),
        "signal_score": lead_data.get("signal_score", 0),
        "source": lead_data.get("source"),
        "last_contacted": lead_data.get("last_contacted"),
    }


def extract_deal_features(deal_data: dict[str, Any]) -> dict[str, Any]:
    """Extract features specifically for deal processing.
    
    Args:
        deal_data: Raw deal data dictionary
        
    Returns:
        Extracted deal features
    """
    return {
        "deal_size": deal_data.get("deal_size"),
        "stage": deal_data.get("stage"),
        "probability": deal_data.get("probability"),
        "age_days": deal_data.get("age_days"),
        "contact_count": deal_data.get("contact_count"),
    }


def extract_contract_features(contract_data: dict[str, Any]) -> dict[str, Any]:
    """Extract features specifically for contract/invoice processing.
    
    Args:
        contract_data: Raw contract data dictionary
        
    Returns:
        Extracted contract features
    """
    return {
        "amount": contract_data.get("amount"),
        "status": contract_data.get("status"),
        "days_pending": contract_data.get("days_pending"),
        "payment_history": contract_data.get("payment_history"),
    }


def features_to_prompt(features: dict[str, Any]) -> str:
    """Convert features dictionary to a prompt-friendly string.
    
    Args:
        features: Extracted features dictionary
        
    Returns:
        Formatted string for LLM prompt
    """
    if not features:
        return "No features available."
    
    parts = []
    for key, value in features.items():
        if value is not None:
            parts.append(f"{key}: {value}")
    
    return "; ".join(parts)
