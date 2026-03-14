# DESIGN RATIONALE

## Simple Explanation
RIVO is designed to automate repetitive revenue tasks while keeping humans in control of high-impact decisions.

It is structured in layers so each part can evolve independently:
- API for access
- Services/agents for behavior
- Database for truth and audit
- Scheduler/tasks for automation

## Technical Explanation

## Why the System Is Designed This Way

### 1) Layered separation
- API handlers in `app/api/v1/endpoints.py` focus on auth, request parsing, and orchestration triggers.
- Business logic lives in services/agents (`app/services/`, `app/agents/`).
- Persistent state transitions are centralized in DB handlers (`app/database/db_handler.py`).

Rationale: reduces coupling and keeps side effects explicit.

### 2) Review-first progression model
- Draft generation and recommendations are separate from stage transitions.
- Progression is guarded by explicit decision functions (`mark_review_decision`, `mark_contract_decision`, `mark_dunning_decision`).

Rationale: human-in-the-loop safety and auditability.

### 3) Dual trigger model (API + scheduler)
- Manual/API path for immediate operation.
- Scheduled path for autonomous runs with concurrency protection.

Rationale: supports both interactive control and unattended operation.

### 4) Fallback-centric resilience
- DB fallback for local/dev continuity.
- Celery fallback wrappers to keep tests/local operation working.
- LLM and RAG fallbacks to deterministic paths.

Rationale: avoid hard system failure when optional dependencies are unavailable.

## Tradeoffs Observed in Code

### Tradeoff A: Simplicity vs strict centralization
- Some write logic exists in both service methods and db_handler helpers.
- Benefit: local clarity in each module.
- Cost: risk of duplicated transition semantics if not maintained consistently.

### Tradeoff B: Flexibility vs route-surface clarity
- Multiple v1 route modules exist, but only `endpoints` and `auth` are mounted.
- Benefit: staged development surface.
- Cost: potential confusion unless mounted set is documented clearly.

### Tradeoff C: Deterministic safety vs model sophistication
- LLM outputs are bounded by schemas/fallbacks and deterministic checks.
- Benefit: predictable behavior.
- Cost: reduced expressiveness when models fail and templates are used.

## Performance/Operability Considerations
- DB session-per-operation pattern is clear but can increase query/session churn.
- Analytics endpoints compute in Python after fetching tenant deals; large datasets may need pagination/aggregation tuning.
- Scheduler sequential chain intentionally prioritizes failure containment over parallel throughput.

## Current Architecture Limitations (Code-evident)
1. Mounted vs unmounted v1 route split can drift without explicit docs.
2. Some legacy/transitional modules coexist with runtime-wired modules.
3. LLM provider is single-path (Ollama endpoint), fallback is deterministic text rather than alternate model provider.
4. In-memory fallbacks (task/runtime helpers) are practical for local/test but not distributed-state substitutes.

## What This Means for Future Extensions
- Keep transition authority centralized.
- Prefer additive service changes before endpoint-level complexity.
- If introducing parallelism, preserve audit and state consistency guarantees.
- If adding model providers, maintain current empty-string/fallback contracts to avoid behavioral regressions.
