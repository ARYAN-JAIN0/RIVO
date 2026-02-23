"""Add negotiation_turn and confidence_score to contracts

Revision ID: 20260219_0004
Revises: 20260215_0003
Create Date: 2026-02-19

This migration adds:
- negotiation_turn: Track number of negotiation rounds (enforces MAX_NEGOTIATION_TURNS)
- confidence_score: Store confidence score from negotiation agent
- tenant_id: Add multi-tenant support to contracts
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260219_0004"
down_revision = "20260215_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add negotiation tracking columns to contracts table."""
    # Add tenant_id column if it doesn't exist
    op.add_column(
        "contracts",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    
    # Add negotiation_turn column
    op.add_column(
        "contracts",
        sa.Column("negotiation_turn", sa.Integer(), nullable=True, default=0),
    )
    
    # Add confidence_score column
    op.add_column(
        "contracts",
        sa.Column("confidence_score", sa.Integer(), nullable=True, default=0),
    )
    
    # Set default values for existing rows
    op.execute("UPDATE contracts SET tenant_id = 1 WHERE tenant_id IS NULL")
    op.execute("UPDATE contracts SET negotiation_turn = 0 WHERE negotiation_turn IS NULL")
    op.execute("UPDATE contracts SET confidence_score = 0 WHERE confidence_score IS NULL")
    
    # Make tenant_id non-nullable after setting defaults
    op.alter_column("contracts", "tenant_id", nullable=False)
    
    # Add foreign key constraint for tenant_id
    op.create_foreign_key(
        "fk_contracts_tenant_id",
        "contracts",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    
    # Add index for tenant_id
    op.create_index(
        "idx_contracts_tenant_id",
        "contracts",
        ["tenant_id"],
    )


def downgrade() -> None:
    """Remove negotiation tracking columns from contracts table."""
    # Drop index
    op.drop_index("idx_contracts_tenant_id", "contracts")
    
    # Drop foreign key
    op.drop_constraint("fk_contracts_tenant_id", "contracts", type_="foreignkey")
    
    # Drop columns
    op.drop_column("contracts", "confidence_score")
    op.drop_column("contracts", "negotiation_turn")
    op.drop_column("contracts", "tenant_id")
