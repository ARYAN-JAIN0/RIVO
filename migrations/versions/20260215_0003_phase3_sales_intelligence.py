"""Phase 3: sales intelligence pipeline, scoring, proposal, analytics, and RAG tables.

Revision ID: 20260215_0003
Revises: 20260214_0002
Create Date: 2026-02-15 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260215_0003"
down_revision = "20260214_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("deals", sa.Column("status", sa.String(), nullable=True, server_default="Open"))
    op.add_column("deals", sa.Column("deal_value", sa.Integer(), nullable=True))
    op.add_column("deals", sa.Column("probability", sa.Float(), nullable=True, server_default="0"))
    op.add_column("deals", sa.Column("expected_close_date", sa.Date(), nullable=True))
    op.add_column("deals", sa.Column("margin", sa.Float(), nullable=True))
    op.add_column("deals", sa.Column("cost_estimate", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("deals", sa.Column("forecast_month", sa.String(), nullable=True))
    op.add_column("deals", sa.Column("segment_tag", sa.String(), nullable=True, server_default="SMB"))
    op.add_column("deals", sa.Column("probability_breakdown", sa.JSON(), nullable=True))
    op.add_column("deals", sa.Column("probability_explanation", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("probability_confidence", sa.Integer(), nullable=True))
    op.add_column("deals", sa.Column("proposal_path", sa.String(), nullable=True))
    op.add_column("deals", sa.Column("proposal_version", sa.Integer(), nullable=True, server_default="0"))
    op.create_index("idx_deals_tenant_stage", "deals", ["tenant_id", "stage"])
    op.create_foreign_key("fk_deals_tenant_id", "deals", "tenants", ["tenant_id"], ["id"])
    op.alter_column("deals", "tenant_id", nullable=False)

    op.create_table(
        "deal_stage_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("old_stage", sa.String(), nullable=False),
        sa.Column("new_stage", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_deal_stage_audit_deal", "deal_stage_audit", ["deal_id"])

    op.create_table(
        "knowledge_base",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("vector", sa.Text(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_base.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "negotiation_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deal_id", sa.Integer(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("objection_tags", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("negotiation_memory")
    op.drop_table("embeddings")
    op.drop_table("knowledge_base")
    op.drop_index("idx_deal_stage_audit_deal", table_name="deal_stage_audit")
    op.drop_table("deal_stage_audit")

    for col in [
        "proposal_version",
        "proposal_path",
        "probability_confidence",
        "probability_explanation",
        "probability_breakdown",
        "segment_tag",
        "forecast_month",
        "cost_estimate",
        "margin",
        "expected_close_date",
        "probability",
        "deal_value",
        "status",
    ]:
        op.drop_column("deals", col)

    op.drop_constraint("fk_deals_tenant_id", "deals", type_="foreignkey")
    op.drop_index("idx_deals_tenant_stage", table_name="deals")
    op.drop_column("deals", "tenant_id")
