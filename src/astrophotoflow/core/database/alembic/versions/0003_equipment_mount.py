"""Add equatorial mounts to the existing equipment registry."""

from alembic import op

revision = "0003_equipment_mount"
down_revision = "0002_image_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("equipment", recreate="always") as batch:
        batch.drop_constraint("ck_equipment_kind", type_="check")
        batch.create_check_constraint("ck_equipment_kind", "kind IN ('camera', 'telescope', 'filter', 'mount')")


def downgrade() -> None:
    raise RuntimeError("Removing mount support requires explicitly resolving registered mounts first.")
