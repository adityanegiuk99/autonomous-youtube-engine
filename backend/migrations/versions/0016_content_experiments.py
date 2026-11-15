"""Add human-managed content experiments."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_content_experiments"
down_revision = "0015_worker_heartbeats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("variable", sa.String(length=80), nullable=False),
        sa.Column("control_description", sa.String(length=500), nullable=False),
        sa.Column("treatment_description", sa.String(length=500), nullable=False),
        sa.Column("metric", sa.String(length=48), nullable=False),
        sa.Column("control_video_ids", sa.JSON(), nullable=False),
        sa.Column("treatment_video_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('planned', 'running', 'completed', 'cancelled')", name="ck_content_experiments_status"),
        sa.CheckConstraint("metric IN ('views', 'click_through_rate_percent', 'average_view_duration_seconds', 'watch_time_minutes', 'likes', 'comments', 'subscribers_gained')", name="ck_content_experiments_metric"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_experiments_channel_created", "content_experiments", ["channel_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_content_experiments_channel_created", table_name="content_experiments")
    op.drop_table("content_experiments")
