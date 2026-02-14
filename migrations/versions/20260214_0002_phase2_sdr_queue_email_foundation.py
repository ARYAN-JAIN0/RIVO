"""Phase 2 foundation: tenant/email/agent run/prompt/llm logging + lead enrichment columns.

Revision ID: 20260214_0002
Revises: 20260213_0001
Create Date: 2026-02-14 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


LEADS_TENANT_EMAIL_UNIQUE = "uq_leads_tenant_email"


revision = "20260214_0002"
down_revision = "20260213_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.execute("INSERT INTO tenants (id, name, is_active, created_at) VALUES (1, 'default', true, CURRENT_TIMESTAMP)")

    op.add_column("leads", sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("leads", sa.Column("website", sa.String(), nullable=True))
    op.add_column("leads", sa.Column("location", sa.String(), nullable=True))
    op.add_column("leads", sa.Column("source", sa.String(), nullable=True, server_default="manual"))
    op.add_column("leads", sa.Column("last_reply_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("followup_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("leads", sa.Column("next_followup_at", sa.DateTime(), nullable=True))
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"])
    op.create_foreign_key("fk_leads_tenant_id", "leads", "tenants", ["tenant_id"], ["id"])
    op.alter_column("leads", "tenant_id", nullable=False)

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = inspector.get_unique_constraints("leads")
    unique_indexes = inspector.get_indexes("leads")
    lead_email_constraint_names = {
        constraint.get("name")
        for constraint in unique_constraints
        if tuple(constraint.get("column_names") or ()) == ("email",)
    }

    # Baseline schema used a named single-column uniqueness guard.
    if "uq_leads_email" in lead_email_constraint_names:
        op.drop_constraint("uq_leads_email", "leads", type_="unique")
    else:
        for name in lead_email_constraint_names:
            if name:
                op.drop_constraint(name, "leads", type_="unique")

    # Some engines expose legacy single-column uniqueness as a unique index.
    lead_email_unique_index_names = {
        index.get("name")
        for index in unique_indexes
        if index.get("unique") and tuple(index.get("column_names") or ()) == ("email",)
    }
    for name in lead_email_unique_index_names:
        if name:
            op.drop_index(name, table_name="leads")

    op.create_unique_constraint(LEADS_TENANT_EMAIL_UNIQUE, "leads", ["tenant_id", "email"])

    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("recipient_email", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tracking_id", sa.String(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("clicked_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracking_id"),
    )
    op.create_index("idx_email_logs_lead", "email_logs", ["lead_id"])
    op.create_index("idx_email_logs_status", "email_logs", ["status"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("idx_agent_runs_agent_status", "agent_runs", ["agent_name", "status"])

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("template_key", sa.String(), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_name", "template_key", name="uq_prompt_template_agent_key"),
    )

    op.create_table(
        "llm_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("validation_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("llm_logs")
    op.drop_table("prompt_templates")
    op.drop_index("idx_agent_runs_agent_status", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("idx_email_logs_status", table_name="email_logs")
    op.drop_index("idx_email_logs_lead", table_name="email_logs")
    op.drop_table("email_logs")

    op.drop_constraint(LEADS_TENANT_EMAIL_UNIQUE, "leads", type_="unique")
    op.create_unique_constraint("uq_leads_email", "leads", ["email"])

    op.drop_constraint("fk_leads_tenant_id", "leads", type_="foreignkey")
    op.drop_index("ix_leads_tenant_id", table_name="leads")
    op.drop_column("leads", "next_followup_at")
    op.drop_column("leads", "followup_count")
    op.drop_column("leads", "last_reply_at")
    op.drop_column("leads", "source")
    op.drop_column("leads", "location")
    op.drop_column("leads", "website")
    op.drop_column("leads", "tenant_id")

    op.drop_table("tenants")
