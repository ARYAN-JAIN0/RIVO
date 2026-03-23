"""RAG document chunks for semantic search

Revision ID: 20260318_0006
Revises: 20260220_0005
Create Date: 2026-03-18 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260318_0006"
down_revision = "20260220_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the rag_document_chunks table
    # Note: Using JSON text for embeddings instead of pgvector for compatibility
    op.create_table(
        "rag_document_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),  # JSON-serialized list
        sa.Column("source_filename", sa.String(500), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for efficient querying
    op.create_index("idx_rag_chunks_tenant_id", "rag_document_chunks", ["tenant_id"])
    op.create_index("idx_rag_chunks_tenant_created", "rag_document_chunks", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_rag_chunks_tenant_created", table_name="rag_document_chunks")
    op.drop_index("idx_rag_chunks_tenant_id", table_name="rag_document_chunks")
    op.drop_table("rag_document_chunks")
