"""Add append-only content workflow event history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_workflow_events"
down_revision = "0009_analytics_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_state", sa.String(length=32), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_idea_id"], ["content_ideas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_events_content_idea_id", "workflow_events", ["content_idea_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_events_content_idea_id", table_name="workflow_events")
    op.drop_table("workflow_events")
