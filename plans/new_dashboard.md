🔒 NON-NEGOTIABLE RULES

All reads are tenant-scoped

All writes go through crm_service.py

All manual mutations log CRM_MANUAL_OVERRIDE

All stage transitions validated

Pagination is server-side

Sorting is server-side

No raw SQL

No bypassing review gates

🏗 BACKEND DESIGN (DETAILED)
1️⃣ Pagination Model

Every list endpoint must accept:

?page=1
&page_size=25
&sort_by=created_at
&sort_order=desc
&search=acme
&status=Contacted

And return:

{
  "items": [...],
  "total": 542,
  "page": 1,
  "page_size": 25,
  "total_pages": 22
}
2️⃣ crm_service.py — Required Methods
LIST METHODS

Each must:

Filter by tenant_id

Apply optional filters

Apply search (ILIKE on key fields)

Apply sorting (safe whitelist only)

Apply offset/limit

Return total count

Required:

get_leads(...)
get_deals(...)
get_contracts(...)
get_invoices(...)
MUTATION METHODS

Each must:

Validate tenant ownership

Validate stage transitions (if applicable)

Log audit

Commit safely

Required:

approve_lead_draft_safe(...)
reject_lead_draft_safe(...)
override_deal_stage_safe(...)
mark_invoice_paid_safe(...)
override_overdue_stage_safe(...)
trigger_agent_safe(...)
3️⃣ Safe Sorting Whitelist

To prevent SQL injection via sort_by:

Each entity must define:

ALLOWED_SORT_FIELDS = {
    "created_at": Model.created_at,
    "status": Model.status,
    "company": Model.company_name,
}

Reject any non-whitelisted sort field.

4️⃣ Tenant Enforcement Pattern

Inside every service method:

if entity.tenant_id != tenant_id:
    raise Forbidden("Cross-tenant access blocked")

Never assume tenant_id is correct.

🖥 STREAMLIT CRM DESIGN

File: app/crm_dashboard.py

Structure:

st.set_page_config(layout="wide")

tabs = st.tabs(["Leads", "Deals", "Contracts", "Invoices"])

Each tab:

Filter row (status dropdown + search input)

Paginated table (page controls)

Action buttons per row

Confirmation modal

API mutation call

st.rerun()

Pagination UI Pattern

Top-right controls:

Page number input

Page size selector (10 / 25 / 50 / 100)

Total records display

🔐 RBAC Requirements

Only allow:

Admin → full access

Sales → leads + deals

Finance → invoices

Viewer → read-only

Enforce at API layer, not Streamlit.