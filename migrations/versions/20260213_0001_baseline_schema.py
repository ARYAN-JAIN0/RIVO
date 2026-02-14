"""baseline schema with review audit and integrity constraints

Revision ID: 20260213_0001
Revises:
Create Date: 2026-02-13 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260213_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("company_size", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("verified_insight", sa.Text(), nullable=True),
        sa.Column("negative_signals", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("last_contacted", sa.DateTime(), nullable=True),
        sa.Column("signal_score", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=True),
        sa.Column("draft_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_leads_status", "leads", ["status"])
    op.create_index("idx_leads_review_status", "leads", ["review_status"])

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("acv", sa.Integer(), nullable=True),
        sa.Column("qualification_score", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_deals_stage", "deals", ["stage"])
    op.create_index("idx_deals_review_status", "deals", ["review_status"])

    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_code", sa.String(), nullable=True),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("contract_terms", sa.Text(), nullable=True),
        sa.Column("negotiation_points", sa.Text(), nullable=True),
        sa.Column("objections", sa.Text(), nullable=True),
        sa.Column("proposed_solutions", sa.Text(), nullable=True),
        sa.Column("signed_date", sa.DateTime(), nullable=True),
        sa.Column("contract_value", sa.Integer(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_code"),
        sa.UniqueConstraint("deal_id", name="uq_contracts_deal_id"),
    )
    op.create_index("idx_contracts_status", "contracts", ["status"])
    op.create_index("idx_contracts_review_status", "contracts", ["review_status"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_code", sa.String(), nullable=True),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("days_overdue", sa.Integer(), nullable=True),
        sa.Column("dunning_stage", sa.Integer(), nullable=True),
        sa.Column("last_contact_date", sa.DateTime(), nullable=True),
        sa.Column("payment_date", sa.DateTime(), nullable=True),
        sa.Column("draft_message", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_code"),
        sa.UniqueConstraint("contract_id", name="uq_invoices_contract_id"),
    )
    op.create_index("idx_invoices_status", "invoices", ["status"])
    op.create_index("idx_invoices_review_status", "invoices", ["review_status"])

    op.create_table(
        "review_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_review_audit_entity", "review_audit", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("idx_review_audit_entity", table_name="review_audit")
    op.drop_table("review_audit")

    op.drop_index("idx_invoices_review_status", table_name="invoices")
    op.drop_index("idx_invoices_status", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("idx_contracts_review_status", table_name="contracts")
    op.drop_index("idx_contracts_status", table_name="contracts")
    op.drop_table("contracts")

    op.drop_index("idx_deals_review_status", table_name="deals")
    op.drop_index("idx_deals_stage", table_name="deals")
    op.drop_table("deals")

    op.drop_index("idx_leads_review_status", table_name="leads")
    op.drop_index("idx_leads_status", table_name="leads")
    op.drop_table("leads")

