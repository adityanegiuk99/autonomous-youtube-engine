"""Bind local publishing schedule metadata to explicit human review."""

from alembic import op
import sqlalchemy as sa


revision = "0018_schedule_metadata_review"
down_revision = "0017_caption_sidecars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publish_jobs", sa.Column("metadata_hash", sa.String(length=64), nullable=True))
    op.add_column("publish_jobs", sa.Column("metadata_reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("publish_jobs", "metadata_reviewed_at")
    op.drop_column("publish_jobs", "metadata_hash")
