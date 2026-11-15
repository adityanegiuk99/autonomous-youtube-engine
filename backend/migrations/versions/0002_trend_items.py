"""Add RSS trend items."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_trend_items"
down_revision = "0001_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trend_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_urls", sa.JSON(), nullable=False),
        sa.Column("article_urls", sa.JSON(), nullable=False),
        sa.Column("trend_score", sa.Float(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trend_items_canonical_key", "trend_items", ["canonical_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_trend_items_canonical_key", table_name="trend_items")
    op.drop_table("trend_items")
