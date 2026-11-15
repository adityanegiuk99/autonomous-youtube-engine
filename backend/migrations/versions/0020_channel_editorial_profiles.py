"""Add channel audience and editorial strategy settings."""

from alembic import op
import sqlalchemy as sa


revision = "0020_channel_editorial_profiles"
down_revision = "0019_script_research_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("audience_profile", sa.Text(), nullable=True))
    op.add_column("channels", sa.Column("brand_voice", sa.Text(), nullable=True))
    op.add_column("channels", sa.Column("visual_guidelines", sa.Text(), nullable=True))
    op.add_column("channels", sa.Column("content_pillars", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("channels", sa.Column("preferred_formats", sa.JSON(), nullable=False, server_default=sa.text("'[\"short\",\"long\"]'")))
    op.add_column("channels", sa.Column("publishing_frequency_per_week", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("channels", "publishing_frequency_per_week")
    op.drop_column("channels", "preferred_formats")
    op.drop_column("channels", "content_pillars")
    op.drop_column("channels", "visual_guidelines")
    op.drop_column("channels", "brand_voice")
    op.drop_column("channels", "audience_profile")
