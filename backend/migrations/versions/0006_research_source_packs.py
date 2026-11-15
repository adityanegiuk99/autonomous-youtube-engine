"""Add RSS summary provenance and versioned research source packs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_research_source_packs"
down_revision = "0005_video_previews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trend_items", sa.Column("summary_source_url", sa.String(length=2048), nullable=True))
    op.create_table(
        "research_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trend_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trend_item_id"], ["trend_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trend_item_id", "version", name="uq_research_trend_version"),
    )
    op.create_index("ix_research_documents_trend_item_id", "research_documents", ["trend_item_id"])


def downgrade() -> None:
    op.drop_index("ix_research_documents_trend_item_id", table_name="research_documents")
    op.drop_table("research_documents")
    op.drop_column("trend_items", "summary_source_url")
