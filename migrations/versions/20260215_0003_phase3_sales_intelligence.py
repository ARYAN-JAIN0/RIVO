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


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def _foreign_key_exists(inspector, table_name: str, fk_name: str) -> bool:
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = sa.inspect(bind)

    deal_columns: list[tuple[str, sa.Column]] = [
        ("tenant_id", sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1")),
        ("status", sa.Column("status", sa.String(), nullable=True, server_default="Open")),
        ("deal_value", sa.Column("deal_value", sa.Integer(), nullable=True)),
        ("probability", sa.Column("probability", sa.Float(), nullable=True, server_default="0")),
        ("expected_close_date", sa.Column("expected_close_date", sa.Date(), nullable=True)),
        ("margin", sa.Column("margin", sa.Float(), nullable=True)),
        ("cost_estimate", sa.Column("cost_estimate", sa.Integer(), nullable=True, server_default="0")),
        ("forecast_month", sa.Column("forecast_month", sa.String(), nullable=True)),
        ("segment_tag", sa.Column("segment_tag", sa.String(), nullable=True, server_default="SMB")),
        ("probability_breakdown", sa.Column("probability_breakdown", sa.JSON(), nullable=True)),
        ("probability_explanation", sa.Column("probability_explanation", sa.Text(), nullable=True)),
        ("probability_confidence", sa.Column("probability_confidence", sa.Integer(), nullable=True)),
        ("proposal_path", sa.Column("proposal_path", sa.String(), nullable=True)),
        ("proposal_version", sa.Column("proposal_version", sa.Integer(), nullable=True, server_default="0")),
    ]

    if dialect_name == "sqlite":
        # SQLite does not support ALTER TABLE ADD CONSTRAINT for foreign keys.
        existing = _column_names(inspector, "deals")
        with op.batch_alter_table("deals", recreate="auto") as batch_op:
            for name, col in deal_columns:
                if name not in existing:
                    batch_op.add_column(col)
            if not _index_exists(inspector, "deals", "idx_deals_tenant_stage"):
                batch_op.create_index("idx_deals_tenant_stage", ["tenant_id", "stage"], unique=False)
    else:
        existing = _column_names(inspector, "deals")
        for name, col in deal_columns:
            if name not in existing:
                op.add_column("deals", col)

        inspector = sa.inspect(bind)
        if not _index_exists(inspector, "deals", "idx_deals_tenant_stage"):
            op.create_index("idx_deals_tenant_stage", "deals", ["tenant_id", "stage"])
        if not _foreign_key_exists(inspector, "deals", "fk_deals_tenant_id"):
            op.create_foreign_key("fk_deals_tenant_id", "deals", "tenants", ["tenant_id"], ["id"])
        op.alter_column("deals", "tenant_id", nullable=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "deal_stage_audit"):
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
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "deal_stage_audit") and not _index_exists(inspector, "deal_stage_audit", "idx_deal_stage_audit_deal"):
        op.create_index("idx_deal_stage_audit_deal", "deal_stage_audit", ["deal_id"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "knowledge_base"):
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
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "knowledge_base") and not _index_exists(inspector, "knowledge_base", "idx_knowledge_base_tenant_entity"):
        op.create_index("idx_knowledge_base_tenant_entity", "knowledge_base", ["tenant_id", "entity_type", "entity_id"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "embeddings"):
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
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "embeddings") and not _index_exists(inspector, "embeddings", "idx_embeddings_knowledge_base"):
        op.create_index("idx_embeddings_knowledge_base", "embeddings", ["knowledge_base_id"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "negotiation_memory"):
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
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "negotiation_memory") and not _index_exists(inspector, "negotiation_memory", "idx_negotiation_memory_deal"):
        op.create_index("idx_negotiation_memory_deal", "negotiation_memory", ["deal_id"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "negotiation_memory"):
        if _index_exists(inspector, "negotiation_memory", "idx_negotiation_memory_deal"):
            op.drop_index("idx_negotiation_memory_deal", table_name="negotiation_memory")
        op.drop_table("negotiation_memory")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "embeddings"):
        if _index_exists(inspector, "embeddings", "idx_embeddings_knowledge_base"):
            op.drop_index("idx_embeddings_knowledge_base", table_name="embeddings")
        op.drop_table("embeddings")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "knowledge_base"):
        if _index_exists(inspector, "knowledge_base", "idx_knowledge_base_tenant_entity"):
            op.drop_index("idx_knowledge_base_tenant_entity", table_name="knowledge_base")
        op.drop_table("knowledge_base")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "deal_stage_audit"):
        if _index_exists(inspector, "deal_stage_audit", "idx_deal_stage_audit_deal"):
            op.drop_index("idx_deal_stage_audit_deal", table_name="deal_stage_audit")
        op.drop_table("deal_stage_audit")

    if dialect_name == "sqlite":
        existing = _column_names(sa.inspect(bind), "deals")
        with op.batch_alter_table("deals", recreate="auto") as batch_op:
            if _index_exists(sa.inspect(bind), "deals", "idx_deals_tenant_stage"):
                batch_op.drop_index("idx_deals_tenant_stage")
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
                "tenant_id",
            ]:
                if col in existing:
                    batch_op.drop_column(col)
    else:
        existing = _column_names(sa.inspect(bind), "deals")
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
            if col in existing:
                op.drop_column("deals", col)

        inspector = sa.inspect(bind)
        if _foreign_key_exists(inspector, "deals", "fk_deals_tenant_id"):
            op.drop_constraint("fk_deals_tenant_id", "deals", type_="foreignkey")
        if _index_exists(inspector, "deals", "idx_deals_tenant_stage"):
            op.drop_index("idx_deals_tenant_stage", table_name="deals")
        if "tenant_id" in _column_names(sa.inspect(bind), "deals"):
            op.drop_column("deals", "tenant_id")
