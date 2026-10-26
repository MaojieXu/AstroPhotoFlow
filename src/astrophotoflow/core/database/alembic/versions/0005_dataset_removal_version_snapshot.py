from alembic import op
import sqlalchemy as sa


revision = "0005_dataset_removal_version_snapshot"
down_revision = "0004_library_entry_removal_and_asset_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "library_entry_removal",
        sa.Column("dataset_version_id", sa.String(length=36), nullable=True),
    )
    with op.batch_alter_table("library_entry_removal") as batch_op:
        batch_op.create_foreign_key(
            "fk_library_entry_removal_dataset_version_id_dataset_version",
            "dataset_version",
            ["dataset_version_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("library_entry_removal") as batch_op:
        batch_op.drop_constraint(
            "fk_library_entry_removal_dataset_version_id_dataset_version",
            type_="foreignkey",
        )
        batch_op.drop_column("dataset_version_id")
