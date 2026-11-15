"""Persist production render attempts for interruption recovery."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013_production_attempts"
down_revision = "0012_local_publish_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storyboard_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("render_duration_seconds", sa.Float(), nullable=True),
        sa.Column("source_bytes", sa.BigInteger(), nullable=True),
        sa.Column("output_bytes", sa.BigInteger(), nullable=True),
        sa.Column("failure_class", sa.String(length=48), nullable=True),
        sa.ForeignKeyConstraint(["content_idea_id"], ["content_ideas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["storyboard_version_id"], ["storyboards.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_production_attempts_storyboard_started", "production_attempts",
                    ["content_idea_id", "storyboard_version_id", "started_at"], unique=False)
    op.create_index("uq_production_attempts_active", "production_attempts",
                    ["content_idea_id", "storyboard_version_id"], unique=True,
                    postgresql_where=sa.text("status = 'running'"), sqlite_where=sa.text("status = 'running'"))


def downgrade() -> None:
    op.drop_index("uq_production_attempts_active", table_name="production_attempts")
    op.drop_index("ix_production_attempts_storyboard_started", table_name="production_attempts")
    op.drop_table("production_attempts")
