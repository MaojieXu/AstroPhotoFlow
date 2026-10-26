from alembic import op
import sqlalchemy as sa


revision = "0006_library_trash_cleanup_state"
down_revision = "0005_dataset_removal_version_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("library_entry_removal", sa.Column("member_asset_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("library_entry_removal", sa.Column("pending_paths", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("library_entry_removal", sa.Column("cleaned_paths", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("library_entry_removal", sa.Column("cleaned_asset_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("library_entry_removal", sa.Column("cleanup_status", sa.String(length=16), nullable=False, server_default="trash"))
    op.add_column("library_entry_removal", sa.Column("cleanup_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("library_entry_removal", "cleanup_error")
    op.drop_column("library_entry_removal", "cleanup_status")
    op.drop_column("library_entry_removal", "cleaned_asset_ids")
    op.drop_column("library_entry_removal", "cleaned_paths")
    op.drop_column("library_entry_removal", "pending_paths")
    op.drop_column("library_entry_removal", "member_asset_ids")
