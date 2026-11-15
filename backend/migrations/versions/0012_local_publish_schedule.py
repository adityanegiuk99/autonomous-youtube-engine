"""Add a local-only schedule for human-approved renders."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_local_publish_schedule"
down_revision = "0011_render_usage_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publish_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("video_id", name="uq_publish_jobs_video"),
    )
    op.create_index(op.f("ix_publish_jobs_video_id"), "publish_jobs", ["video_id"], unique=False)
    op.create_index(op.f("ix_publish_jobs_channel_id"), "publish_jobs", ["channel_id"], unique=False)
    op.create_index(op.f("ix_publish_jobs_scheduled_at"), "publish_jobs", ["scheduled_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_publish_jobs_scheduled_at"), table_name="publish_jobs")
    op.drop_index(op.f("ix_publish_jobs_channel_id"), table_name="publish_jobs")
    op.drop_index(op.f("ix_publish_jobs_video_id"), table_name="publish_jobs")
    op.drop_table("publish_jobs")
