"""Add imported channel analytics snapshots."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_analytics_snapshots"
down_revision = "0008_human_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_video_id", sa.String(length=128), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "external_video_id", "collected_at", name="uq_analytics_channel_video_date"),
    )
    op.create_index("ix_analytics_snapshots_channel_id", "analytics_snapshots", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_analytics_snapshots_channel_id", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")
