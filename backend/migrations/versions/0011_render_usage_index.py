"""Index workflow render events for operational summaries."""
from alembic import op

revision = "0011_render_usage_index"
down_revision = "0010_workflow_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_workflow_events_type_created", "workflow_events", ["event_type", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_events_type_created", table_name="workflow_events")
