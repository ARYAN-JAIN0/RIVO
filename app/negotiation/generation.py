"""Generation layer for negotiation responses.

This module generates negotiation responses using LLM with template-based fallback.
It includes conversation history, objection type, selected strategy, and RAG context
in the prompt.

This module follows the LLM separation rule:
- LLM → generation ONLY
- System → validation, scoring, decisions (done in other modules)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.services.llm_client import call_llm

logger = logging.getLogger(__name__)


# Template-based fallback responses by strategy
FALLBACK_TEMPLATES = {
    "DISCOUNT": [
        "I understand budget is a concern. Let me check what options we have for committed annual agreements that could provide better value.",
        "We want to make this work for you. Would you be open to discussing a multi-year agreement that could reduce the effective cost?",
    ],
    "VALUE_REINFORCEMENT": [
        "Based on similar companies in your industry, they typically see significant ROI within the first year. Would it help to walk through some of those case studies?",
        "The value proposition here goes beyond the core features. Let me highlight some of the additional benefits that often get overlooked.",
    ],
    "URGENCY": [
        "I want to make sure you're aware that this pricing is available for the next {days} days. After that, we'll need to adjust based on our new pricing structure.",
        "Given your mentioned timeline, starting now would allow you to capture the full benefits before year-end. Shall we lock in the current terms?",
    ],
    "DEFERRAL": [
        "I completely understand this is a big decision. Would it be helpful to schedule a call with your team to answer any questions before you need to decide?",
        "Let's plan to reconnect once you have more clarity. In the meantime, I can send over some materials that might help with your internal discussions.",
    ],
}


@dataclass
class GenerationResult:
    """Result of response generation."""
    response: str
    method: str  # "llm" or "template_fallback"
    strategy: str


def _build_prompt(
    objection_text: str,
    conversation_history: list[dict],
    objection_type: str,
    strategy: str,
    deal_context: dict,
    rag_context: list[str],
) -> str:
    """Build the prompt for LLM response generation.
    
    Args:
        objection_text: The customer's objection.
        conversation_history: Previous messages in the conversation.
        objection_type: Classified objection type.
        strategy: Selected negotiation strategy.
        deal_context: Deal information (company, value, etc.).
        rag_context: Retrieved context from RAG.
        
    Returns:
        Formatted prompt string.
    """
    # Format conversation history
    history_text = ""
    if conversation_history:
        history_lines = []
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = msg.get("role", "unknown")
            text = msg.get("message_text", "")
            history_lines.append(f"{role.upper()}: {text}")
        history_text = "\n".join(history_lines)
    
    # Format deal context
    company = deal_context.get("company", "Your Company")
    deal_value = deal_context.get("deal_value", 0)
    contact_name = deal_context.get("contact_name", "there")
    
    # Format RAG context
    rag_text = ""
    if rag_context:
        rag_text = "\nRelevant context:\n" + "\n".join(f"- {ctx}" for ctx in rag_context[:3])
    
    # Build the prompt
    prompt = f"""You are a Senior Sales Negotiator at RevoAI. Your goal is to handle customer objections professionally and move the deal forward.

CONTEXT:
- Company: {company}
- Deal Value: ${deal_value:,}
- Contact: {contact_name}
- Objection Type: {objection_type}
- Strategy: {strategy}

CONVERSATION HISTORY:
{history_text or "No previous messages"}

CUSTOMER OBJECTION:
{objection_text}

{rag_text}

INSTRUCTIONS:
1. Respond to the objection using the {strategy} strategy
2. Keep the response concise (2-4 sentences) and natural
3. Do NOT include signatures or sign-offs like "Best," or "Regards,"
4. Focus on addressing the specific objection
5. If offering a discount, be vague about exact numbers ("some flexibility")
6. If using urgency, reference time-sensitive factors naturally

Output JSON only:
{{
  "response": "Your negotiation response here..."
}}"""
    
    return prompt


def _generate_with_template(strategy: str) -> str:
    """Generate response using template fallback.
    
    Args:
        strategy: The selected negotiation strategy.
        
    Returns:
        Template-based response string.
    """
    templates = FALLBACK_TEMPLATES.get(strategy, FALLBACK_TEMPLATES["VALUE_REINFORCEMENT"])
    
    import random
    response = random.choice(templates)
    
    # Fill in template variables
    from datetime import datetime, timedelta
    if "{days}" in response:
        days = random.randint(7, 30)
        response = response.replace("{days}", str(days))
    
    logger.info(
        "negotiation.generation.template_used",
        extra={
            "event": "negotiation.generation.template_used",
            "strategy": strategy,
        },
    )
    
    return response


def generate_response(
    objection_text: str,
    conversation_history: list[dict],
    objection_type: str,
    strategy: str,
    deal_context: dict | None = None,
    rag_context: list[str] | None = None,
) -> GenerationResult:
    """Generate a negotiation response using LLM with template fallback.
    
    This function implements the generation layer:
    1. Builds prompt with all context (history, objection, strategy, RAG)
    2. Attempts LLM generation
    3. Falls back to template-based response if LLM fails
    
    Args:
        objection_text: The customer's objection.
        conversation_history: Previous messages in the conversation.
        objection_type: Classified objection type.
        strategy: Selected negotiation strategy.
        deal_context: Deal information (company, value, etc.).
        rag_context: Retrieved context from RAG.
        
    Returns:
        GenerationResult with response and method used.
    """
    # Prepare context
    ctx = deal_context or {}
    rag = rag_context or []
    
    # Build prompt
    prompt = _build_prompt(
        objection_text=objection_text,
        conversation_history=conversation_history,
        objection_type=objection_type,
        strategy=strategy,
        deal_context=ctx,
        rag_context=rag,
    )
    
    # Try LLM generation
    response = call_llm(prompt, json_mode=True)
    
    if response:
        try:
            data = json.loads(response)
            generated = data.get("response", "").strip()
            
            if generated and len(generated) > 10:
                logger.info(
                    "negotiation.generation.llm_success",
                    extra={
                        "event": "negotiation.generation.llm_success",
                        "strategy": strategy,
                        "response_length": len(generated),
                    },
                )
                return GenerationResult(
                    response=generated,
                    method="llm",
                    strategy=strategy,
                )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(
                "negotiation.generation.llm_parse_failed",
                extra={
                    "event": "negotiation.generation.llm_parse_failed",
                    "error": str(e),
                },
            )
    
    # Fall back to template-based response
    fallback = _generate_with_template(strategy)
    
    logger.warning(
        "negotiation.generation.llm_failed",
        extra={
            "event": "negotiation.generation.llm_failed",
            "fallback_used": True,
            "strategy": strategy,
        },
    )
    
    return GenerationResult(
        response=fallback,
        method="template_fallback",
        strategy=strategy,
    )
