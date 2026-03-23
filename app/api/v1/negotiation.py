"""API endpoints for the negotiation system.

This module provides:
- POST /negotiation/respond - Full negotiation flow (classify, strategize, generate, score)
- GET /negotiation/history/{deal_id} - Conversation retrieval

All endpoints require authentication and enforce tenant isolation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.api._compat import APIRouter, Header, HTTPException, status
from sqlalchemy.orm import selectinload

from app.api.v1._authz import authorize, map_auth_error
from app.database.db import get_db_session
from app.database.models import Deal, NegotiationMessage
from app.negotiation.classification import classify_objection
from app.negotiation.contract_updates import get_contract_constraints
from app.negotiation.generation import generate_response
from app.negotiation.scoring import score_response
from app.negotiation.strategy import select_strategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/negotiation", tags=["Negotiation"])


# Request/Response models
class NegotiationRespondRequest(BaseModel):
    """Request for negotiation response generation."""
    deal_id: int = Field(..., description="The deal ID")
    objection_text: str = Field(..., min_length=1, description="Customer's objection or message")
    message_type: str = Field(default="objection", description="Type of message: objection, offer")


class NegotiationRespondResponse(BaseModel):
    """Response from negotiation flow."""
    deal_id: int
    response_text: str
    objection_type: str
    strategy: str
    scores: dict[str, int]
    requires_human_review: bool
    message_id: int | None = None


class NegotiationHistoryItem(BaseModel):
    """Single message in conversation history."""
    role: str
    message_text: str
    message_type: str
    detected_intent: str | None
    timestamp: str


class NegotiationHistoryResponse(BaseModel):
    """Conversation history for a deal."""
    deal_id: int
    messages: list[NegotiationHistoryItem]
    total_count: int


def _authorize(authorization: str | None, scopes: list[str]):
    """Helper to authorize requests."""
    try:
        return authorize(authorization=authorization, scopes=scopes)
    except Exception as exc:
        code, detail = map_auth_error(exc)
        raise HTTPException(status_code=code, detail=detail) from exc


def _get_deal_context(deal_id: int, tenant_id: int) -> dict[str, Any] | None:
    """Get deal context for negotiation."""
    with get_db_session() as session:
        deal = (
            session.query(Deal)
            .options(selectinload(Deal.lead))
            .filter(
                Deal.id == deal_id,
                Deal.tenant_id == tenant_id
            )
            .first()
        )
        
        if not deal:
            return None
        
        return {
            "company": deal.company or "Unknown Company",
            "deal_value": deal.deal_value or deal.acv or 0,
            "contact_name": deal.lead.name if deal.lead else "there",
            "stage": deal.stage,
        }


def _get_conversation_history(deal_id: int, tenant_id: int, limit: int = 10) -> list[dict]:
    """Get conversation history for a deal."""
    with get_db_session() as session:
        messages = (
            session.query(NegotiationMessage)
            .filter(
                NegotiationMessage.deal_id == deal_id,
                NegotiationMessage.tenant_id == tenant_id
            )
            .order_by(NegotiationMessage.timestamp.desc())
            .limit(limit)
            .all()
        )
        
        # Reverse to get chronological order
        return [
            {
                "role": msg.role,
                "message_text": msg.message_text,
                "message_type": msg.message_type,
                "detected_intent": msg.detected_intent,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
            }
            for msg in reversed(messages)
        ]


def _save_message(
    deal_id: int,
    tenant_id: int,
    role: str,
    message_text: str,
    message_type: str,
    detected_intent: str | None = None,
) -> int:
    """Save a negotiation message to the database."""
    with get_db_session() as session:
        msg = NegotiationMessage(
            tenant_id=tenant_id,
            deal_id=deal_id,
            role=role,
            message_text=message_text,
            message_type=message_type,
            detected_intent=detected_intent,
            timestamp=datetime.utcnow(),
        )
        session.add(msg)
        session.commit()
        
        logger.info(
            "negotiation.message.saved",
            extra={
                "event": "negotiation.message.saved",
                "deal_id": deal_id,
                "role": role,
                "message_type": message_type,
                "message_id": msg.id,
            },
        )
        
        return msg.id


@router.post("/respond", response_model=NegotiationRespondResponse)
def negotiation_respond(
    request: NegotiationRespondRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> NegotiationRespondResponse:
    """Execute the full negotiation flow.
    
    This endpoint:
    1. Classifies the objection (rule-based with LLM fallback)
    2. Selects a negotiation strategy
    3. Generates a response (LLM with template fallback)
    4. Scores the response
    5. Saves the message to history
    
    Returns the generated response along with classification,
    strategy, and scoring information.
    """
    user = _authorize(authorization, scopes=["negotiation.respond"])
    tenant_id = user.tenant_id
    
    # Get deal context
    deal_context = _get_deal_context(request.deal_id, tenant_id)
    if not deal_context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )
    
    # Get conversation history
    history = _get_conversation_history(request.deal_id, tenant_id)
    
    # Get previous strategy (for avoidance)
    previous_strategy = None
    for msg in reversed(history):
        if msg["role"] == "agent" and msg.get("detected_intent"):
            # Store last strategy used (simplified - would need to store in message)
            break
    
    # Step 1: Classify the objection
    classification = classify_objection(
        text=request.objection_text,
        context=deal_context,
    )
    
    logger.info(
        "negotiation.flow.classification",
        extra={
            "event": "negotiation.flow.classification",
            "deal_id": request.deal_id,
            "objection_type": classification.objection_type,
            "confidence": classification.confidence,
            "method": classification.method,
        },
    )
    
    # Step 2: Select strategy
    strategy_result = select_strategy(
        objection_type=classification.objection_type,
        deal_context=deal_context,
        previous_strategy=previous_strategy,
    )
    
    logger.info(
        "negotiation.flow.strategy",
        extra={
            "event": "negotiation.flow.strategy",
            "deal_id": request.deal_id,
            "strategy": strategy_result.strategy,
        },
    )
    
    # Step 3: Generate response
    generation = generate_response(
        objection_text=request.objection_text,
        conversation_history=history,
        objection_type=classification.objection_type,
        strategy=strategy_result.strategy,
        deal_context=deal_context,
        rag_context=None,  # Could integrate RAG here
    )
    
    logger.info(
        "negotiation.flow.generation",
        extra={
            "event": "negotiation.flow.generation",
            "deal_id": request.deal_id,
            "method": generation.method,
            "response_length": len(generation.response),
        },
    )
    
    # Step 4: Score the response
    scoring = score_response(
        response=generation.response,
        objection=request.objection_text,
        strategy=strategy_result.strategy,
    )
    
    logger.info(
        "negotiation.flow.scoring",
        extra={
            "event": "negotiation.flow.scoring",
            "deal_id": request.deal_id,
            "total_score": scoring.total_score,
            "requires_review": scoring.requires_human_review,
        },
    )
    
    # Step 5: Save messages to history
    # Save user message
    user_msg_id = _save_message(
        deal_id=request.deal_id,
        tenant_id=tenant_id,
        role="user",
        message_text=request.objection_text,
        message_type=request.message_type,
        detected_intent=classification.objection_type,
    )
    
    # Save agent response
    agent_msg_id = _save_message(
        deal_id=request.deal_id,
        tenant_id=tenant_id,
        role="agent",
        message_text=generation.response,
        message_type="response",
        detected_intent=strategy_result.strategy,
    )
    
    return NegotiationRespondResponse(
        deal_id=request.deal_id,
        response_text=generation.response,
        objection_type=classification.objection_type,
        strategy=strategy_result.strategy,
        scores={
            "total": scoring.total_score,
            "strategy_alignment": scoring.strategy_alignment,
            "relevance": scoring.relevance,
            "coherence": scoring.coherence,
        },
        requires_human_review=scoring.requires_human_review,
        message_id=agent_msg_id,
    )


@router.get("/history/{deal_id}", response_model=NegotiationHistoryResponse)
def get_negotiation_history(
    deal_id: int,
    limit: int = 50,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> NegotiationHistoryResponse:
    """Get conversation history for a deal.
    
    Returns all messages in the negotiation conversation,
    ordered by timestamp (oldest first).
    """
    user = _authorize(authorization, scopes=["negotiation.history.read"])
    tenant_id = user.tenant_id
    
    # Verify deal exists and belongs to tenant
    with get_db_session() as session:
        deal = session.query(Deal).filter(
            Deal.id == deal_id,
            Deal.tenant_id == tenant_id
        ).first()
        
        if not deal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found",
            )
    
    # Get messages
    history = _get_conversation_history(deal_id, tenant_id, limit)
    
    return NegotiationHistoryResponse(
        deal_id=deal_id,
        messages=[
            NegotiationHistoryItem(
                role=msg["role"],
                message_text=msg["message_text"],
                message_type=msg["message_type"],
                detected_intent=msg.get("detected_intent"),
                timestamp=msg["timestamp"],
            )
            for msg in history
        ],
        total_count=len(history),
    )


@router.get("/constraints/{deal_id}")
def get_negotiation_constraints(
    deal_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Get contract constraints for a deal.
    
    Returns pricing and timeline constraints for negotiation.
    """
    user = _authorize(authorization, scopes=["negotiation.constraints.read"])
    tenant_id = user.tenant_id
    
    with get_db_session() as session:
        deal = session.query(Deal).filter(
            Deal.id == deal_id,
            Deal.tenant_id == tenant_id
        ).first()
        
        if not deal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found",
            )
        
        # Find associated contract
        if deal.contracts:
            contract = deal.contracts[0]
            return {
                "deal_id": deal_id,
                "current_value": deal.deal_value or deal.acv or 0,
                "min_value": 1000,
                "max_discount_percent": 20,
                "current_close_date": deal.expected_close_date.isoformat() if deal.expected_close_date else None,
                "negotiation_turn": contract.negotiation_turn or 0 if contract else 0,
            }
        
        return {
            "deal_id": deal_id,
            "current_value": deal.deal_value or deal.acv or 0,
            "min_value": 1000,
            "max_discount_percent": 20,
            "current_close_date": deal.expected_close_date.isoformat() if deal.expected_close_date else None,
            "negotiation_turn": 0,
        }
