"""Remove the retired independent capture preset entities.

Revision ID: 0004_remove_capture_presets
Revises: 0003_equipment_mount
"""

from alembic import op

revision = "0004_remove_capture_presets"
down_revision = "0003_equipment_mount"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_preset_selection_member", table_name="capture_preset_selection")
    op.drop_table("capture_preset_selection")
    op.drop_index("ix_capture_preset_name_search_key", table_name="capture_preset")
    op.drop_table("capture_preset")


def downgrade() -> None:
    raise RuntimeError("Capture presets were retired; restore the pre-upgrade database backup to recover them.")
