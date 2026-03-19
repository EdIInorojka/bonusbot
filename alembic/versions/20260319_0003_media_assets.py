"""add media assets table"""

from alembic import op
import sqlalchemy as sa


revision = "20260319_0003"
down_revision = "20260319_0002"
branch_labels = None
depends_on = None


mediaassettype = sa.Enum("file_id", "url", name="mediaassettype")


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("asset_type", mediaassettype, nullable=False, server_default="file_id"),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_assets")),
    )


def downgrade() -> None:
    op.drop_table("media_assets")
    op.execute("DROP TYPE IF EXISTS mediaassettype")
