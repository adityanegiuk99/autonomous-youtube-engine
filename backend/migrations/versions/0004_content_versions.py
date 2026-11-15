"""Add immutable script and storyboard versions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_content_versions"
down_revision = "0003_content_ideas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("origin", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_idea_id"], ["content_ideas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_idea_id", "version", name="uq_scripts_idea_version"),
    )
    op.create_index("ix_scripts_content_idea_id", "scripts", ["content_idea_id"])
    op.create_table(
        "storyboards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_idea_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("script_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("scenes", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_idea_id"], ["content_ideas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["script_version_id"], ["scripts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_idea_id", "version", name="uq_storyboards_idea_version"),
    )
    op.create_index("ix_storyboards_content_idea_id", "storyboards", ["content_idea_id"])


def downgrade() -> None:
    op.drop_index("ix_storyboards_content_idea_id", table_name="storyboards")
    op.drop_table("storyboards")
    op.drop_index("ix_scripts_content_idea_id", table_name="scripts")
    op.drop_table("scripts")
