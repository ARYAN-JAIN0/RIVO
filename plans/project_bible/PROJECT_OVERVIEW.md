# PROJECT OVERVIEW (MASTER INDEX)

## MRCE L1 — Objective Formalizer
Repository understanding goal: fully reconstruct the repository into the Project Bible so any LLM can answer repo-level questions without accessing source files.
Primary goal: complete, deterministic, and code-accurate Project Bible coverage for all repository files.
Secondary goals: enable downstream LLM reasoning, remove dependency on the repo, improve interpretability and extension safety.
Constraints: no missing files; no shallow summaries; no assumptions without grounding; deterministic structure.
Assumptions: repository is accessible; existing Project Bible set is the authoritative documentation target.
Success criteria: any LLM can answer repo-level queries with ≥95% accuracy; all modules, flows, and dependencies documented.
Failure conditions: missing modules or files; vague or unverifiable descriptions; unclear architecture; incomplete flows.

## MRCE L2 — Deterministic Planner
Phase 1: repository enumeration using deterministic file inventory and category grouping.
Phase 2: file-level analysis for every file with purpose, inputs, outputs, key components, dependencies, logic summary, and edge cases.
Phase 3: system-level reconstruction of architecture, data flow, control flow, and agent interactions.
Phase 4: knowledge compression into structured, non-redundant blocks.
Phase 5: Project Bible integration by mapping required sections to existing documents.
Phase 6: validation checkpoints for coverage completeness, logical consistency, and dependency integrity.

## MRCE L3 — Knowledge Execution Output Contract
The Project Bible is expressed as a multi-file master document set under `plans/project_bible/`.
All 20 required sections are present and explicitly mapped in the section index below.

## MRCE L4 — Structural Validation Gate
Coverage completeness is enforced by a deterministic file list and a per-file breakdown entry for each file.

## MRCE L5 — Domain Critic
Weak areas are reinforced with explicit rules, edge cases, and validation guidance.

## MRCE L6 — Optimization Engine
Redundancy is minimized through cross-references while preserving complete semantic coverage.

## MRCE L7 — Confidence & Risk Scoring
Coverage score: 255/255 files (100%).
Confidence level: High.
Missing or uncertain areas: binary artifact contents are documented via metadata only; logs are summarized structurally.
Risk zones: AI generation fallbacks, scheduler concurrency guards, and review-gate transitions.

## Project Bible Section Map (1–20)
| Section | Title | Location |
| --- | --- | --- |
| 1 | Repository Overview | `PROJECT_OVERVIEW.md` |
| 2 | Complete File & Folder Map | `FILE_STRUCTURE_GUIDE.md` |
| 3 | File-by-File Breakdown | `FILE_STRUCTURE_GUIDE.md` |
| 4 | System Architecture | `SYSTEM_ARCHITECTURE.md` |
| 5 | Data Flow | `DATA_FLOW_EXPLAINED.md` |
| 6 | Control Flow | `SYSTEM_ARCHITECTURE.md` |
| 7 | Core Modules & Responsibilities | `MODULE_DEEP_DIVE.md` |
| 8 | Dependency Graph | `FUNCTION_REFERENCE.md` |
| 9 | Business Logic & Rules | `MODULE_DEEP_DIVE.md` |
| 10 | Error Handling & Failure Modes | `MAINTENANCE_GUIDE.md` |
| 11 | Configuration & Environment | `MAINTENANCE_GUIDE.md` |
| 12 | AI / Agent Logic | `AI_ALGORITHM_LOGIC.md` |
| 13 | Security & Access Control | `SYSTEM_ARCHITECTURE.md` |
| 14 | Feature Set | `PROJECT_OVERVIEW.md` |
| 15 | Extension Guide | `MAINTENANCE_GUIDE.md` |
| 16 | Debugging Playbook | `MAINTENANCE_GUIDE.md` |
| 17 | Known Limitations | `PROJECT_OVERVIEW.md` |
| 18 | Future Improvements | `PROJECT_OVERVIEW.md` |
| 19 | Glossary | `PROJECT_OVERVIEW.md` |
| 20 | LLM Usability Layer | `SIMPLIFIED_EXPLANATION.md` |

## 1. Repository Overview
Project name: RIVO (Revenue Lifecycle Autopilot).
Purpose: automate and orchestrate a multi-stage B2B revenue workflow with human review gates.
Problem solved: reliable, auditable lead-to-cash progression with AI assistance and deterministic fallbacks.
Target users: revenue operations teams, SDR/sales/finance operators, and internal automation maintainers.
High-level functionality: lead acquisition, SDR drafting, sales qualification, negotiation strategy, invoicing and dunning, all gated by review decisions.

## 14. Feature Set
End-to-end pipeline with stage agents (SDR, Sales, Negotiation, Finance) and orchestrator sequencing.
Manual and scheduled execution paths with Celery and scheduler fallbacks.
Review-gated transitions with audit logging and CRM-style API endpoints.
AI-assisted text generation with deterministic fallbacks and validation.
RAG ingestion and retrieval with embedding fallback.
Operational dashboards (Streamlit) and analytics endpoints.
Tenant-scoped data isolation and JWT-based auth.

## 17. Known Limitations
Mounted v1 route surface is narrower than the full set of available route modules.
Some services duplicate logic between service layer and db handler transitions.
Single LLM provider path (Ollama); fallbacks are deterministic, not alternate providers.
Analytics endpoints compute in Python and may need aggregation optimization for large datasets.
Scheduler runs sequentially and prioritizes failure containment over throughput.

## 18. Future Improvements
Add multi-provider LLM abstraction with identical failure contract.
Introduce batched analytics queries or database-level aggregation.
Optional parallelization of pipeline stages with stricter state locks.
Consolidate duplicated transition logic into a single source of truth.

## 19. Glossary
Agent: a stage executor that processes one pipeline step (SDR, Sales, Negotiation, Finance).
Review gate: explicit human decision step that controls status transitions.
Draft: generated content stored pending review (email, negotiation response, dunning note).
AgentRun: execution record tracking agent/task outcomes.
RAG: retrieval-augmented generation using stored knowledge snippets.

## Coverage Validation Checklist
Inventory method: `rg --files` plus explicit hidden/tooling files and runtime artifacts; `.git` and `.venv` are excluded as non-repository environment state.
Total files enumerated: 255.
Counts by category (top-level or explicit groups):
Root files: 17.
Application code (`app/`): 123.
Tests (`tests/`): 36.
Scripts (`scripts/` + root run scripts): 14.
Docs and plans (`docs/`, `plans/`): 28.
Migrations (`migrations/`): 7.
Configs (`config/`, `.env*`, `alembic.ini`, `.github`, `.vscode`, `.claude`, `.kilocode`): 16.
Data and artifacts (`db/`, `.db`, `.log`, `celerybeat-schedule.*`, `proposals/`, `certs/`): 14.
Coverage complete marker: ALL_ENUMERATED_FILES_PRESENT_IN_BREAKDOWN.
