"""Add uploaded media provenance and production QA metadata."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_media_assets_and_qa"
down_revision = "0006_research_source_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("asset_type", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("license_type", sa.String(length=32), nullable=False),
        sa.Column("rights_confirmed", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.add_column("videos", sa.Column("video_type", sa.String(length=24), nullable=False, server_default="animatic"))
    op.add_column("videos", sa.Column("thumbnail_key", sa.String(length=80), nullable=True))
    op.add_column("videos", sa.Column("media_manifest", sa.JSON(), nullable=True))
    op.add_column("videos", sa.Column("qa_report", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "qa_report")
    op.drop_column("videos", "media_manifest")
    op.drop_column("videos", "thumbnail_key")
    op.drop_column("videos", "video_type")
    op.drop_table("media_assets")
