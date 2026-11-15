"""Add scored channel content ideas."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_content_ideas"
down_revision = "0002_trend_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trend_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("trend_velocity", sa.Float(), nullable=False),
        sa.Column("engagement_potential", sa.Float(), nullable=False),
        sa.Column("audience_relevance", sa.Float(), nullable=False),
        sa.Column("originality", sa.Float(), nullable=False),
        sa.Column("research_quality", sa.Float(), nullable=False),
        sa.Column("competition", sa.Float(), nullable=True),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trend_item_id"], ["trend_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_ideas_channel_id", "content_ideas", ["channel_id"])
    op.create_index("ix_content_ideas_trend_item_id", "content_ideas", ["trend_item_id"])


def downgrade() -> None:
    op.drop_index("ix_content_ideas_trend_item_id", table_name="content_ideas")
    op.drop_index("ix_content_ideas_channel_id", table_name="content_ideas")
    op.drop_table("content_ideas")
