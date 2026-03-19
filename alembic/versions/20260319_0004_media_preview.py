"""add media preview url"""

from alembic import op
import sqlalchemy as sa


revision = "20260319_0004"
down_revision = "20260319_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("preview_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("media_assets", "preview_url")
