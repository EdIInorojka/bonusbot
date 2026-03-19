"""init schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0001"
down_revision = None
branch_labels = None
depends_on = None


userrole = sa.Enum("user", "admin", name="userrole")
prizetype = sa.Enum(
    "free_spins",
    "deposit_bonus",
    "cashback",
    "promo_code",
    "usdt",
    "fp",
    "custom",
    name="prizetype",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("language_code", sa.String(length=10), nullable=True),
        sa.Column("ref_code", sa.String(length=24), nullable=False),
        sa.Column("referred_by_id", sa.BigInteger(), nullable=True),
        sa.Column("funnel_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("balance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_spins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("role", userrole, nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["referred_by_id"], ["users.id"], name=op.f("fk_users_referred_by_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("ref_code", name=op.f("uq_users_ref_code")),
    )
    op.create_index(op.f("ix_users_ref_code"), "users", ["ref_code"], unique=False)
    op.create_index(op.f("ix_users_referred_by_id"), "users", ["referred_by_id"], unique=False)

    op.create_table(
        "admin_settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_admin_settings")),
    )

    op.create_table(
        "prizes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_text", sa.Text(), nullable=False),
        sa.Column("prize_type", prizetype, nullable=False),
        sa.Column("value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("per_user_limit", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prizes")),
    )

    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referrer_id", sa.BigInteger(), nullable=False),
        sa.Column("referral_id", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["referral_id"], ["users.id"], name=op.f("fk_referrals_referral_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"], name=op.f("fk_referrals_referrer_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referrals")),
        sa.UniqueConstraint("referrer_id", "referral_id", "level", name="uq_referral_chain"),
    )
    op.create_index(op.f("ix_referrals_referrer_id"), "referrals", ["referrer_id"], unique=False)
    op.create_index(op.f("ix_referrals_referral_id"), "referrals", ["referral_id"], unique=False)
    op.create_index(op.f("ix_referrals_level"), "referrals", ["level"], unique=False)

    op.create_table(
        "spin_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("prize_id", sa.Integer(), nullable=True),
        sa.Column("won", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reward_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_key", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("spin_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["prize_id"], ["prizes.id"], name=op.f("fk_spin_history_prize_id_prizes"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_spin_history_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spin_history")),
    )
    op.create_index(op.f("ix_spin_history_user_id"), "spin_history", ["user_id"], unique=False)
    op.create_index(op.f("ix_spin_history_prize_id"), "spin_history", ["prize_id"], unique=False)
    op.create_index(op.f("ix_spin_history_session_key"), "spin_history", ["session_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_spin_history_session_key"), table_name="spin_history")
    op.drop_index(op.f("ix_spin_history_prize_id"), table_name="spin_history")
    op.drop_index(op.f("ix_spin_history_user_id"), table_name="spin_history")
    op.drop_table("spin_history")

    op.drop_index(op.f("ix_referrals_level"), table_name="referrals")
    op.drop_index(op.f("ix_referrals_referral_id"), table_name="referrals")
    op.drop_index(op.f("ix_referrals_referrer_id"), table_name="referrals")
    op.drop_table("referrals")

    op.drop_table("prizes")
    op.drop_table("admin_settings")

    op.drop_index(op.f("ix_users_referred_by_id"), table_name="users")
    op.drop_index(op.f("ix_users_ref_code"), table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS prizetype")
    op.execute("DROP TYPE IF EXISTS userrole")
