"""Add content-bound human approval records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_human_approvals"
down_revision = "0007_media_assets_and_qa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("reviewer", sa.String(length=120), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("review_checks", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_video_id", "approvals", ["video_id"])


def downgrade() -> None:
    op.drop_index("ix_approvals_video_id", table_name="approvals")
    op.drop_table("approvals")
    op.drop_column("videos", "content_hash")
