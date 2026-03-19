"""add bot chat state table"""

from alembic import op
import sqlalchemy as sa


revision = "20260319_0002"
down_revision = "20260319_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_chat_state",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("last_bot_message_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_bot_chat_state")),
    )
    op.create_index(op.f("ix_bot_chat_state_chat_id"), "bot_chat_state", ["chat_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bot_chat_state_chat_id"), table_name="bot_chat_state")
    op.drop_table("bot_chat_state")
