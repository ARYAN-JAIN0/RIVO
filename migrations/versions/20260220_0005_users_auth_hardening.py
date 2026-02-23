"""Create users table for DB-backed authentication.

Revision ID: 20260220_0005
Revises: 20260219_0004
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260220_0005"
down_revision = "20260219_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default=sa.text("'viewer'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("idx_users_tenant_role", "users", ["tenant_id", "role"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_users_tenant_role", table_name="users")
    op.drop_table("users")
