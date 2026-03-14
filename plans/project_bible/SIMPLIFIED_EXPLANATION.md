# SIMPLIFIED EXPLANATION

## Simple Explanation
RIVO is like an automated revenue operations assembly line with human checkpoints.

### Real-world analogy
- **Lead acquisition** is like collecting new customer cards.
- **SDR** is the assistant drafting first outreach emails.
- **Sales** is the rep qualifying serious opportunities.
- **Negotiation** is the specialist handling objections.
- **Finance** is billing and payment follow-up.

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

## Why this matters for non-technical users
- You get faster execution without losing control.
- Approvals are auditable.
- Pipeline status is visible by stage.
- Failures in AI services do not fully stop operations.

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
