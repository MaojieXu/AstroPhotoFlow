"""Keep batch requests for automatically generated library thumbnails."""
import sqlalchemy as sa
from alembic import op

revision = "0006_library_thumbnails"
down_revision = "0005_master_calibration_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thumbnail_batch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index("ix_thumbnail_batch_created", "thumbnail_batch", ["created_at"])
    op.create_table(
        "thumbnail_batch_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("thumbnail_batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preview_id", sa.String(36), sa.ForeignKey("preview.id", ondelete="SET NULL")),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id", ondelete="SET NULL")),
        sa.Column("dataset_version_id", sa.String(36), sa.ForeignKey("dataset_version.id", ondelete="SET NULL")),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("batch_id", "position", name="uq_thumbnail_batch_position"),
    )
    op.create_index("ix_thumbnail_batch_item_preview", "thumbnail_batch_item", ["preview_id"])


def downgrade() -> None:
    op.drop_table("thumbnail_batch_item")
    op.drop_table("thumbnail_batch")
