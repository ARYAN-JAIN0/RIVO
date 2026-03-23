# AI ALGORITHM LOGIC

## 12. AI / Agent Logic

### Simple Explanation
RIVO uses AI where language generation helps productivity, then backs it with deterministic checks and fallbacks. If AI is unavailable, the system still runs with template/rule behavior.

### Technical Explanation

#### LLM text generation (Ollama)
- Core client call: `call_llm(prompt, json_mode)` in `app/services/llm_client.py`.
- Model and endpoint resolved from config: `OLLAMA_MODEL`, `OLLAMA_GENERATE_URL`.
- Failure contract: returns empty string `""` on failure.

#### Embeddings + retrieval (RAG)
- Service: `RAGService` in `app/services/rag_service.py`.
- Primary embedding path: `OllamaEmbeddingProvider.embed()`.
- Fallback path: hash embedding (`_hash_embed()`).
- Retrieval path: cosine similarity and rerank.

#### SDR AI Logic
Generation:
- `generate_email_body()` builds prompt, calls LLM, validates JSON, falls back to deterministic template.
Evaluation:
- `evaluate_email()` combines deterministic score with optional LLM score (0.6/0.4 weighting).
Deterministic controls:
- `validate_structure()` for email format.
- `check_negative_gate()` and `calculate_signal_score()` for gating and scoring.

#### Negotiation AI Logic
- `classify_objections()` creates deterministic objection categories.
- `generate_objection_response()` generates strategy and confidence; falls back on parse failure.

#### Finance AI Logic
- `generate_dunning_email()` generates dunning text and falls back to template.

#### Opportunity Scoring (Hybrid)
- `OpportunityScoringService` combines rule score and LLM score (0.6/0.4).
- Explanation generation is deterministic.

#### Deterministic-only Areas
Lead negative gate and signal scoring, review decision transitions, invoice overdue calculations, middleware auth/rate limiting.

#### AI Reliability and Fallback Boundaries
1. LLM failure returns empty string; callers must handle.
2. Negotiation/finance generation have explicit template fallbacks.
3. RAG can operate in hash-embedding mode when embeddings are unavailable.
4. State transitions remain deterministic and DB-backed.
