"""Add explicit ISO and gain mode to capture profiles."""
from alembic import op
import sqlalchemy as sa

revision = "0003_capture_profile_gain_mode"
down_revision = "0002_asset_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("capture_profile", sa.Column("parameter_mode", sa.String(16), nullable=True))
    op.add_column("capture_profile", sa.Column("iso", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("capture_profile", "iso")
    op.drop_column("capture_profile", "parameter_mode")
