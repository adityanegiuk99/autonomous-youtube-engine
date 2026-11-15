"""Keep queued and running production attempts unique per storyboard."""

from alembic import op
import sqlalchemy as sa


revision = "0014_production_queue_claims"
down_revision = "0013_production_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_production_attempts_active", table_name="production_attempts")
    op.create_index("uq_production_attempts_active", "production_attempts",
                    ["content_idea_id", "storyboard_version_id"], unique=True,
                    postgresql_where=sa.text("status IN ('queued', 'running')"),
                    sqlite_where=sa.text("status IN ('queued', 'running')"))


def downgrade() -> None:
    op.drop_index("uq_production_attempts_active", table_name="production_attempts")
    op.create_index("uq_production_attempts_active", "production_attempts",
                    ["content_idea_id", "storyboard_version_id"], unique=True,
                    postgresql_where=sa.text("status = 'running'"),
                    sqlite_where=sa.text("status = 'running'"))
