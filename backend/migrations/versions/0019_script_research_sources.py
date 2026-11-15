"""Persist research source snapshots with script versions."""

from alembic import op
import sqlalchemy as sa


revision = "0019_script_research_sources"
down_revision = "0018_schedule_metadata_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scripts", sa.Column("source_references", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("scripts", "source_references")
