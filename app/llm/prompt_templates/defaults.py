"""Default prompt templates used by LLM orchestrator scaffolding."""

from __future__ import annotations


def render_sdr_email_prompt(context: dict) -> str:
    return (
        "You are an SDR assistant.\n"
        f"Lead name: {context.get('lead_name', 'Unknown')}\n"
        f"Company: {context.get('company', 'Unknown')}\n"
        "Return a concise outreach draft in JSON."
    )


def render_finance_dunning_prompt(context: dict) -> str:
    return (
        "You are a finance assistant.\n"
        f"Invoice code: {context.get('invoice_code', 'INV-UNKNOWN')}\n"
        f"Amount: {context.get('amount', 0)}\n"
        "Return a professional dunning email in JSON."
    )


DEFAULT_PROMPT_REGISTRY = {
    "sdr.outreach": render_sdr_email_prompt,
    "finance.dunning": render_finance_dunning_prompt,
}

