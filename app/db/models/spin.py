from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.prize import Prize
    from app.db.models.user import User


class SpinHistory(Base, TimestampMixin):
    __tablename__ = "spin_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    prize_id: Mapped[int | None] = mapped_column(ForeignKey("prizes.id", ondelete="SET NULL"), nullable=True, index=True)

    won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reward_value: Mapped[float] = mapped_column(default=0.0, nullable=False)

    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cooldown_until: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payload_type = JSON().with_variant(JSONB, "postgresql")
    payload: Mapped[dict[str, Any]] = mapped_column(payload_type, default=dict, nullable=False)
    spin_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user: Mapped["User"] = relationship(back_populates="spins", lazy="selectin")
    prize: Mapped["Prize | None"] = relationship(back_populates="spins", lazy="selectin")
