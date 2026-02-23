# Production Readiness Implementation Plan

## Overview

This plan addresses all critical gaps and immediate actions identified in the Phase 1-3 audit to make RIVO production-ready.

## Implementation Tasks

### 1. RAG Service - Real Embeddings Integration

**Files to Modify:**
- `app/services/rag_service.py` - Integrate Ollama embedder
- `app/rag/embeddings/ollama_embedder.py` - Ensure proper implementation

**Changes:**
- Replace `_hash_embed()` with real Ollama embeddings
- Add fallback to hash embeddings when Ollama unavailable
- Add embedding caching for performance
- Add proper error handling and logging

### 2. Tenant Context Enforcement

**Files to Modify:**
- `app/database/db_handler.py` - Add tenant_id parameter to all queries
- `app/core/dependencies.py` - Add tenant context dependency
- `app/api/v1/endpoints.py` - Pass tenant_id to all db_handler calls

**Changes:**
- Add `tenant_id` parameter to all db_handler functions
- Create `get_tenant_id()` dependency for FastAPI
- Update all callers to pass tenant context

### 3. Rate Limiting Middleware

**Files to Create:**
- `app/middleware/rate_limit.py` - Rate limiting middleware

**Files to Modify:**
- `app/main.py` - Add middleware to app
- `requirements.txt` - Add slowapi dependency

**Changes:**
- Implement IP-based rate limiting
- Add configurable limits per endpoint
- Add rate limit headers to responses

### 4. Negotiation Turn Limit Enforcement

**Files to Modify:**
- `app/agents/negotiation_agent.py` - Add turn counter
- `app/database/models.py` - Add negotiation_turn column to Contract

**Changes:**
- Add `negotiation_turn` field to Contract model
- Check turn limit before processing
- Log when limit reached

### 5. Correlation ID Middleware

**Files to Create:**
- `app/middleware/correlation.py` - Correlation ID middleware

**Files to Modify:**
- `app/main.py` - Add middleware to app
- `app/core/logging.py` - Include correlation ID in logs

**Changes:**
- Generate unique request ID for each request
- Add X-Request-ID header to responses
- Include in all log entries

### 6. Requirements Update

**Files to Modify:**
- `requirements.txt` - Add missing dependencies

**Dependencies to Add:**
- reportlab (for PDF generation)
- slowapi (for rate limiting)

### 7. Tracking Endpoint Authentication

**Files to Modify:**
- `app/api/v1/endpoints.py` - Add optional auth to tracking endpoints

**Changes:**
- Add optional authentication
- Add rate limiting specifically for tracking endpoints
- Log all tracking requests

### 8. Dead/Duplicate Cleanup Status (Completed)

**Completed Deletions:**
- `app/services/contracts_service.py` (duplicate of contract_service.py)
- `app/services/deals_service.py` (duplicate of deal_service.py)
- `app/services/invoices_service.py` (duplicate of invoice_service.py)
- `app/services/leads_service.py` (duplicate of lead_service.py)
- `app/workers/scheduler.py` and `app/workers/__init__.py` (deprecated wrapper package)
- `db/schema.sql` (legacy SQL artifact, not source of truth)

### 9. Add Comprehensive Tests

**Files to Create:**
- `tests/unit/test_rate_limiting.py`
- `tests/unit/test_correlation_middleware.py`
- `tests/unit/test_rag_embeddings.py`
- `tests/unit/test_tenant_enforcement.py`
- `tests/integration/test_production_readiness.py`

### 10. Add Documentation

**Files to Create:**
- `docs/PRODUCTION_DEPLOYMENT.md` - Deployment guide
- `docs/API_SECURITY.md` - Security documentation

**Files to Modify:**
- All modified files - Add comprehensive docstrings

### 11. Add Logging and Monitoring

**Files to Modify:**
- `app/core/logging_config.py` - Enhanced logging
- All agents - Add structured logging
- `app/main.py` - Add health check endpoints

### 12. Update Manual Tasks

**Files to Modify:**
- `MANUAL_TASKS_REQUIRED.md` - Add new manual steps

---

## Human Intervention Required

The following tasks require manual intervention:

1. **Install Ollama** - Download from https://ollama.ai for real embeddings
2. **Pull embedding model** - Run `ollama pull nomic-embed-text`
3. **Set environment variables** - Configure production secrets
4. **Run migrations** - `alembic upgrade head` after model changes
5. **Configure Redis** - For rate limiting backend in production

---

## Execution Order

1. Add dependencies to requirements.txt
2. Create middleware modules (rate limiting, correlation)
3. Update database models (add negotiation_turn)
4. Create migration for new column
5. Update RAG service with real embeddings
6. Update db_handler with tenant enforcement
7. Update negotiation agent with turn limit
8. Validate dead/duplicate cleanup remains intact
9. Add comprehensive tests
10. Add documentation
11. Update manual tasks file

