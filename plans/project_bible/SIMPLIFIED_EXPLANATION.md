# SIMPLIFIED EXPLANATION

## Simple Explanation
RIVO is an automated revenue operations assembly line with human checkpoints.

### Real-world analogy
- Lead acquisition is like collecting new customer cards.
- SDR drafts first outreach emails.
- Sales qualifies serious opportunities.
- Negotiation handles objections.
- Finance handles billing and payment follow-up.

Nothing moves to the next major stage without an approval decision where required.

## Step-by-step: Day in the life
1. New leads are added to the system.
2. SDR logic reviews each lead and writes an email draft.
3. The draft is reviewed (approved/rejected/blocked).
4. Approved leads become contacted leads.
5. Sales logic creates/updates deals and estimates win probability.
6. Strong deals move to proposal stage.
7. Negotiation logic drafts objection-handling strategy.
8. Approved contracts become signed.
9. Finance logic creates invoices and overdue reminders if needed.
10. Payment status is tracked and can be marked paid.

## Technical Explanation (Plain but Accurate)
- API and scheduler both trigger the same core stage agents.
- Database tables store each entity state (`Lead`, `Deal`, `Contract`, `Invoice`).
- Review decisions are persisted and audited.
- AI helps generate text, but deterministic logic controls progression rules.

Key runtime anchors:
- Orchestration: `app/orchestrator.py:34`
- Primary API routes: `app/api/v1/endpoints.py:59`
- Scheduler automation: `app/tasks/scheduler.py:193`
- Review transition authority: `app/database/db_handler.py:129`, `app/database/db_handler.py:351`, `app/database/db_handler.py:488`

## 20. LLM Usability Layer
Compressed summary for small models:
RIVO is a four-stage pipeline with explicit review gates. Agents generate drafts, but state transitions only occur via decision functions in `db_handler`. Tasks and scheduler run the same stages as API-triggered paths. LLM calls can fail and return empty strings; fallbacks are deterministic.

Key reasoning anchors:
Pipeline order: SDR -> Sales -> Negotiation -> Finance.
Review gate authority: `mark_review_decision`, `mark_contract_decision`, `mark_dunning_decision`.
Fallback contract: `call_llm()` returns empty string on failure.
DB fallback: optional SQLite fallback when Postgres is unavailable.

If X -> check Y mappings:
If drafts exist but statuses do not advance -> check review decision functions and review_status fields.
If scheduler does not run -> check `_is_pipeline_enabled()` and active run guard.
If AI output is empty -> check `call_llm()` return handling and fallback templates.
If API auth fails -> check JWT secret, token expiry, and `_authz.authorize()` scopes.
