"""Store generated WebVTT caption sidecars."""

from alembic import op
import sqlalchemy as sa


revision = "0017_caption_sidecars"
down_revision = "0016_content_experiments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("captions_key", sa.String(length=96), nullable=True))
    op.add_column("videos", sa.Column("captions_checksum", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "captions_checksum")
    op.drop_column("videos", "captions_key")
