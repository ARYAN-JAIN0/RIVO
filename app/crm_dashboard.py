"""
RIVO CRM Dashboard - Streamlit UI

A comprehensive CRM dashboard for managing Leads, Deals, Contracts, and Invoices.

Features:
- Paginated tables with server-side sorting
- Tenant isolation
- Status filtering and search
- Action buttons for mutations
- Audit logging via CRM_MANUAL_OVERRIDE

Usage:
    streamlit run app/crm_dashboard.py
"""

import streamlit as st
from pathlib import Path
import sys
import math

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.crm_service import (
    CRMService,
    InvalidSortFieldError,
    InvalidStatusError,
    LEAD_SORT_FIELDS,
    DEAL_SORT_FIELDS,
    CONTRACT_SORT_FIELDS,
    INVOICE_SORT_FIELDS,
    LEAD_STATUS_VALUES,
    DEAL_STAGE_VALUES,
    CONTRACT_STATUS_VALUES,
    INVOICE_STATUS_VALUES,
)
from app.core.enums import LeadStatus, DealStage, ContractStatus, InvoiceStatus
from app.core.logging_config import configure_logging

configure_logging()

# Page config
st.set_page_config(
    page_title="RIVO CRM Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: 600;
    }
    .pagination-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 8px;
        padding: 15px;
        margin: 5px 0;
    }
    .action-button {
        margin: 2px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize service
crm_service = CRMService()

# Sidebar
with st.sidebar:
    st.title("RIVO CRM")
    st.markdown("---")
    
    # Tenant selection (in production, this would come from auth)
    tenant_id = st.number_input("Tenant ID", value=1, min_value=1, step=1)
    
    st.markdown("### Navigation")
    st.markdown("Use the tabs below to navigate between entities.")
    
    st.markdown("---")
    st.markdown("### Status Reference")
    st.markdown("**Lead Status:**")
    for status in LEAD_STATUS_VALUES:
        st.markdown(f"- {status}")
    
    st.markdown("**Deal Stages:**")
    for stage in DEAL_STAGE_VALUES:
        st.markdown(f"- {stage}")
    
    st.markdown("**Contract Status:**")
    for status in CONTRACT_STATUS_VALUES:
        st.markdown(f"- {status}")
    
    st.markdown("**Invoice Status:**")
    for status in INVOICE_STATUS_VALUES:
        st.markdown(f"- {status}")

# Title
st.title("RIVO CRM Dashboard")
st.markdown(f"Managing data for **Tenant {tenant_id}**")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["Leads", "Deals", "Contracts", "Invoices"])


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def render_pagination(total: int, page: int, page_size: int, key_prefix: str):
    """Render pagination controls and return new page/page_size values."""
    total_pages = math.ceil(total / page_size) if page_size > 0 else 0
    
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    
    with col1:
        if st.button("◀◀ First", key=f"{key_prefix}_first") and page > 1:
            page = 1
            st.rerun()
    
    with col2:
        if st.button("◀ Prev", key=f"{key_prefix}_prev") and page > 1:
            page -= 1
            st.rerun()
    
    with col3:
        st.markdown(f"<div style='text-align: center; padding-top: 8px;'>Page {page} of {total_pages} | Total: {total}</div>", unsafe_allow_html=True)
    
    with col4:
        if st.button("Next ▶", key=f"{key_prefix}_next") and page < total_pages:
            page += 1
            st.rerun()
    
    with col5:
        if st.button("Last ▶▶", key=f"{key_prefix}_last") and page < total_pages:
            page = total_pages
            st.rerun()
    
    return page


def get_page_size_selector(key_prefix: str, default: int = 25) -> int:
    """Render page size selector and return selected value."""
    return st.selectbox(
        "Page Size",
        options=[10, 25, 50, 100],
        index=[10, 25, 50, 100].index(default),
        key=f"{key_prefix}_page_size"
    )


# ==============================================================================
# TAB 1: LEADS
# ==============================================================================

with tab1:
    st.header("Leads")
    
    # Initialize session state for pagination
    if "leads_page" not in st.session_state:
        st.session_state.leads_page = 1
    if "leads_page_size" not in st.session_state:
        st.session_state.leads_page_size = 25
    
    # Filters
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    with col1:
        lead_search = st.text_input("Search", placeholder="Name, email, company...", key="leads_search")
    with col2:
        lead_status = st.selectbox("Status", ["All"] + LEAD_STATUS_VALUES, key="leads_status_filter")
    with col3:
        lead_sort_by = st.selectbox("Sort By", list(LEAD_SORT_FIELDS.keys()), key="leads_sort_by")
    with col4:
        lead_sort_order = st.selectbox("Order", ["desc", "asc"], key="leads_sort_order")
    
    # Page size - widget manages its own session state via key
    page_size = get_page_size_selector("leads", st.session_state.leads_page_size)
    
    # Fetch data
    try:
        result = crm_service.get_leads(
            tenant_id=tenant_id,
            page=st.session_state.leads_page,
            page_size=page_size,
            sort_by=lead_sort_by,
            sort_order=lead_sort_order,
            search=lead_search if lead_search else None,
            status=lead_status if lead_status != "All" else None,
        )
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Leads", result.total)
        with col2:
            st.metric("Current Page", f"{result.page}/{result.total_pages}")
        with col3:
            st.metric("Page Size", result.page_size)
        
        # Display table
        if result.items:
            st.dataframe(
                result.items,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "name": st.column_config.TextColumn("Name", width="medium"),
                    "email": st.column_config.TextColumn("Email", width="medium"),
                    "company": st.column_config.TextColumn("Company", width="medium"),
                    "status": st.column_config.TextColumn("Status", width="small"),
                    "signal_score": st.column_config.NumberColumn("Signal Score", width="small"),
                    "confidence_score": st.column_config.NumberColumn("Confidence", width="small"),
                }
            )
            
            # Action buttons
            st.markdown("### Actions")
            for item in result.items[:5]:  # Show actions for first 5 items
                col1, col2, col3 = st.columns([2, 1, 3])
                with col1:
                    st.markdown(f"**{item.get('name', 'N/A')}** ({item.get('company', 'N/A')})")
                with col2:
                    st.markdown(f"Status: {item.get('status', 'N/A')}")
                with col3:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Approve", key=f"approve_lead_{item['id']}"):
                            try:
                                lead = crm_service.approve_lead_draft_safe(
                                    tenant_id=tenant_id,
                                    lead_id=item["id"],
                                    actor="CRM_DASHBOARD"
                                )
                                if lead:
                                    st.success(f"Lead {item['id']} approved!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    with c2:
                        if st.button("Reject", key=f"reject_lead_{item['id']}"):
                            try:
                                lead = crm_service.reject_lead_draft_safe(
                                    tenant_id=tenant_id,
                                    lead_id=item["id"],
                                    reason="Rejected via CRM Dashboard",
                                    actor="CRM_DASHBOARD"
                                )
                                if lead:
                                    st.warning(f"Lead {item['id']} rejected!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
        else:
            st.info("No leads found matching your criteria.")
        
        # Pagination
        st.session_state.leads_page = render_pagination(
            result.total, st.session_state.leads_page, page_size, "leads"
        )
        
    except (InvalidSortFieldError, InvalidStatusError) as e:
        st.error(f"Error: {e}")


# ==============================================================================
# TAB 2: DEALS
# ==============================================================================

with tab2:
    st.header("Deals")
    
    # Initialize session state for pagination
    if "deals_page" not in st.session_state:
        st.session_state.deals_page = 1
    if "deals_page_size" not in st.session_state:
        st.session_state.deals_page_size = 25
    
    # Filters
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    with col1:
        deal_search = st.text_input("Search", placeholder="Company...", key="deals_search")
    with col2:
        deal_stage = st.selectbox("Stage", ["All"] + DEAL_STAGE_VALUES, key="deals_stage_filter")
    with col3:
        deal_sort_by = st.selectbox("Sort By", list(DEAL_SORT_FIELDS.keys()), key="deals_sort_by")
    with col4:
        deal_sort_order = st.selectbox("Order", ["desc", "asc"], key="deals_sort_order")
    
    # Page size - widget manages its own session state via key
    page_size = get_page_size_selector("deals", st.session_state.deals_page_size)
    
    # Fetch data
    try:
        result = crm_service.get_deals(
            tenant_id=tenant_id,
            page=st.session_state.deals_page,
            page_size=page_size,
            sort_by=deal_sort_by,
            sort_order=deal_sort_order,
            search=deal_search if deal_search else None,
            stage=deal_stage if deal_stage != "All" else None,
        )
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Deals", result.total)
        with col2:
            total_value = sum(item.get("deal_value", 0) or 0 for item in result.items)
            st.metric("Page Value", f"${total_value:,}")
        with col3:
            avg_probability = sum(item.get("probability", 0) or 0 for item in result.items) / len(result.items) if result.items else 0
            st.metric("Avg Probability", f"{avg_probability:.1f}%")
        
        # Display table
        if result.items:
            st.dataframe(
                result.items,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "company": st.column_config.TextColumn("Company", width="medium"),
                    "stage": st.column_config.TextColumn("Stage", width="small"),
                    "deal_value": st.column_config.NumberColumn("Value", format="$%d", width="small"),
                    "probability": st.column_config.NumberColumn("Probability", format="%.1f%%", width="small"),
                    "expected_close_date": st.column_config.TextColumn("Close Date", width="small"),
                }
            )
            
            # Stage override
            st.markdown("### Override Deal Stage")
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                deal_id_input = st.number_input("Deal ID", min_value=1, step=1, key="deal_id_override")
            with col2:
                new_stage = st.selectbox("New Stage", DEAL_STAGE_VALUES, key="deal_new_stage")
            with col3:
                override_reason = st.text_input("Reason", key="deal_override_reason")
            
            if st.button("Override Stage", key="override_deal_btn"):
                try:
                    deal = crm_service.override_deal_stage_safe(
                        tenant_id=tenant_id,
                        deal_id=deal_id_input,
                        new_stage=new_stage,
                        reason=override_reason,
                        actor="CRM_DASHBOARD"
                    )
                    if deal:
                        st.success(f"Deal {deal_id_input} stage changed to {new_stage}!")
                        st.rerun()
                    else:
                        st.error("Deal not found.")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No deals found matching your criteria.")
        
        # Pagination
        st.session_state.deals_page = render_pagination(
            result.total, st.session_state.deals_page, page_size, "deals"
        )
        
    except (InvalidSortFieldError, InvalidStatusError) as e:
        st.error(f"Error: {e}")


# ==============================================================================
# TAB 3: CONTRACTS
# ==============================================================================

with tab3:
    st.header("Contracts")
    
    # Initialize session state for pagination
    if "contracts_page" not in st.session_state:
        st.session_state.contracts_page = 1
    if "contracts_page_size" not in st.session_state:
        st.session_state.contracts_page_size = 25
    
    # Filters
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        contract_status = st.selectbox("Status", ["All"] + CONTRACT_STATUS_VALUES, key="contracts_status_filter")
    with col2:
        contract_sort_by = st.selectbox("Sort By", list(CONTRACT_SORT_FIELDS.keys()), key="contracts_sort_by")
    with col3:
        contract_sort_order = st.selectbox("Order", ["desc", "asc"], key="contracts_sort_order")
    
    # Page size - widget manages its own session state via key
    page_size = get_page_size_selector("contracts", st.session_state.contracts_page_size)
    
    # Fetch data
    try:
        result = crm_service.get_contracts(
            tenant_id=tenant_id,
            page=st.session_state.contracts_page,
            page_size=page_size,
            sort_by=contract_sort_by,
            sort_order=contract_sort_order,
            status=contract_status if contract_status != "All" else None,
        )
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Contracts", result.total)
        with col2:
            total_value = sum(item.get("contract_value", 0) or 0 for item in result.items)
            st.metric("Page Value", f"${total_value:,}")
        with col3:
            signed_count = sum(1 for item in result.items if item.get("status") == "Signed")
            st.metric("Signed", signed_count)
        
        # Display table
        if result.items:
            st.dataframe(
                result.items,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "contract_code": st.column_config.TextColumn("Code", width="small"),
                    "deal_id": st.column_config.NumberColumn("Deal ID", width="small"),
                    "status": st.column_config.TextColumn("Status", width="small"),
                    "contract_value": st.column_config.NumberColumn("Value", format="$%d", width="small"),
                    "confidence_score": st.column_config.NumberColumn("Confidence", width="small"),
                }
            )
            
            # Sign contract action
            st.markdown("### Sign Contract")
            col1, col2 = st.columns([2, 4])
            with col1:
                contract_id_input = st.number_input("Contract ID", min_value=1, step=1, key="contract_id_sign")
            with col2:
                st.markdown("")  # Spacer
            
            if st.button("Mark as Signed", key="sign_contract_btn"):
                try:
                    contract = crm_service.sign_contract_safe(
                        tenant_id=tenant_id,
                        contract_id=contract_id_input,
                        actor="CRM_DASHBOARD"
                    )
                    if contract:
                        st.success(f"Contract {contract_id_input} marked as signed!")
                        st.rerun()
                    else:
                        st.error("Contract not found.")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No contracts found matching your criteria.")
        
        # Pagination
        st.session_state.contracts_page = render_pagination(
            result.total, st.session_state.contracts_page, page_size, "contracts"
        )
        
    except (InvalidSortFieldError, InvalidStatusError) as e:
        st.error(f"Error: {e}")


# ==============================================================================
# TAB 4: INVOICES
# ==============================================================================

with tab4:
    st.header("Invoices")
    
    # Initialize session state for pagination
    if "invoices_page" not in st.session_state:
        st.session_state.invoices_page = 1
    if "invoices_page_size" not in st.session_state:
        st.session_state.invoices_page_size = 25
    
    # Filters
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        invoice_status = st.selectbox("Status", ["All"] + INVOICE_STATUS_VALUES, key="invoices_status_filter")
    with col2:
        invoice_sort_by = st.selectbox("Sort By", list(INVOICE_SORT_FIELDS.keys()), key="invoices_sort_by")
    with col3:
        invoice_sort_order = st.selectbox("Order", ["desc", "asc"], key="invoices_sort_order")
    
    # Page size - widget manages its own session state via key
    page_size = get_page_size_selector("invoices", st.session_state.invoices_page_size)
    
    # Fetch data
    try:
        result = crm_service.get_invoices(
            tenant_id=tenant_id,
            page=st.session_state.invoices_page,
            page_size=page_size,
            sort_by=invoice_sort_by,
            sort_order=invoice_sort_order,
            status=invoice_status if invoice_status != "All" else None,
        )
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Invoices", result.total)
        with col2:
            total_amount = sum(item.get("amount", 0) or 0 for item in result.items)
            st.metric("Page Amount", f"${total_amount:,}")
        with col3:
            overdue_count = sum(1 for item in result.items if item.get("status") == "Overdue")
            st.metric("Overdue", overdue_count)
        
        # Display table
        if result.items:
            st.dataframe(
                result.items,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", width="small"),
                    "invoice_code": st.column_config.TextColumn("Code", width="small"),
                    "contract_id": st.column_config.NumberColumn("Contract ID", width="small"),
                    "amount": st.column_config.NumberColumn("Amount", format="$%d", width="small"),
                    "due_date": st.column_config.TextColumn("Due Date", width="small"),
                    "status": st.column_config.TextColumn("Status", width="small"),
                    "days_overdue": st.column_config.NumberColumn("Days Overdue", width="small"),
                }
            )
            
            # Mark paid action
            st.markdown("### Mark Invoice Paid")
            col1, col2 = st.columns([2, 4])
            with col1:
                invoice_id_input = st.number_input("Invoice ID", min_value=1, step=1, key="invoice_id_paid")
            with col2:
                st.markdown("")  # Spacer
            
            if st.button("Mark as Paid", key="mark_paid_btn"):
                try:
                    invoice = crm_service.mark_invoice_paid_safe(
                        tenant_id=tenant_id,
                        invoice_id=invoice_id_input,
                        actor="CRM_DASHBOARD"
                    )
                    if invoice:
                        st.success(f"Invoice {invoice_id_input} marked as paid!")
                        st.rerun()
                    else:
                        st.error("Invoice not found.")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No invoices found matching your criteria.")
        
        # Pagination
        st.session_state.invoices_page = render_pagination(
            result.total, st.session_state.invoices_page, page_size, "invoices"
        )
        
    except (InvalidSortFieldError, InvalidStatusError) as e:
        st.error(f"Error: {e}")


# ==============================================================================
# FOOTER
# ==============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>RIVO CRM Dashboard | All mutations are logged with CRM_MANUAL_OVERRIDE</p>
    <p>Non-negotiable rules: Tenant isolation | No raw SQL | Review gates preserved</p>
</div>
""", unsafe_allow_html=True)
