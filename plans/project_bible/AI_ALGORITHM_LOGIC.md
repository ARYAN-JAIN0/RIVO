# AI ALGORITHM LOGIC

## Simple Explanation
RIVO uses AI where language generation helps productivity, then backs it with deterministic checks and fallbacks.

If AI is unavailable, the system still runs with template/rule behavior.

## Technical Explanation

## AI Components Present

### 1) LLM text generation (Ollama)
- Core client call: `call_llm(prompt, json_mode)` in `app/services/llm_client.py:29`.
- Model and endpoint resolved from config:
  - `OLLAMA_MODEL`
  - `OLLAMA_GENERATE_URL`
- Failure contract:
  - returns empty string `""` on failure after retry/fast-fail logic.

### 2) Embeddings + retrieval (RAG)
- Service: `RAGService` in `app/services/rag_service.py:279`.
- Primary embedding path:
  - `OllamaEmbeddingProvider.embed()` (`app/services/rag_service.py:228`).
- Fallback path:
  - hash embedding provider (`_hash_embed()` at `app/services/rag_service.py:101`).
- Retrieval path:
  - semantic similarity with cosine (`_cosine()` at `app/services/rag_service.py:120`) and `retrieve()` (`app/services/rag_service.py:549`).

## SDR AI Logic

### Generation
- Function: `generate_email_body()` in `app/agents/sdr_agent.py:138`
- Steps:
  1. Render prompt (`_generation_prompt()` at `app/agents/sdr_agent.py:114`)
  2. Call LLM in JSON mode
  3. Validate/repair parse via schema parsing
  4. Fallback to deterministic template when needed (`build_fallback_email_body()` at `app/agents/sdr_agent.py:101`)

### Evaluation
- Function: `evaluate_email()` in `app/agents/sdr_agent.py:177`
- Algorithm:
  - deterministic quality score (`deterministic_email_quality_score`)
  - optional LLM score parsed from JSON
  - blended final score: `0.6 deterministic + 0.4 llm`

### Deterministic controls around AI
- structural validator: `validate_structure()` in `app/utils/validators.py:33`
- negative gate + signal scoring are deterministic (`app/agents/sdr_agent.py:45`, `app/agents/sdr_agent.py:75`).

## Negotiation AI Logic
- Generation function: `generate_objection_response()` in `app/agents/negotiation_agent.py:91`
- Input shaping:
  - deterministic objection classification via `classify_objections()` (`app/agents/negotiation_agent.py:74`)
- Output handling:
  - parse strategy + confidence
  - fallback to framework-based structured response on parse/failure.

## Finance AI Logic
- Generation function: `generate_dunning_email()` in `app/agents/finance_agent.py:68`
- Deterministic context fields:
  - invoice id, amount, days overdue, stage tone.
- Output handling:
  - parse with `DunningGeneration` schema
  - fallback to stage-specific template text if AI fails.

## Opportunity Scoring Logic (Hybrid)
- Service: `OpportunityScoringService` in `app/services/opportunity_scoring_service.py:41`
- Deterministic part:
  - `_rule_score()` (`app/services/opportunity_scoring_service.py:66`)
- AI part:
  - `_llm_score()` (`app/services/opportunity_scoring_service.py:89`)
- Combined probability:
  - `final_probability = 0.6 * rule_score + 0.4 * llm_score` (`score()` at `app/services/opportunity_scoring_service.py:250`)
- Explanation generation:
  - deterministic factor explanations via `_generate_explanation()` (`app/services/opportunity_scoring_service.py:115`).

## Deterministic-only Areas (No AI Requirement)
- Lead negative gate and signal scoring
- Stage transition validity checks
- Review decision transitions
- Invoice overdue stage calculation
- Middleware auth/rate limiting/correlation

## AI Reliability and Fallback Boundaries
1. LLM text path can fail safely because callers handle empty-string response.
2. Negotiation/finance generation have explicit template fallback.
3. RAG can operate in hash-embedding mode if Ollama embeddings are unavailable.
4. State transitions remain deterministic and DB-backed regardless of AI success.
