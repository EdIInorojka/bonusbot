import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.spin import SpinHistory


class PrizeType(str, enum.Enum):
    free_spins = "free_spins"
    deposit_bonus = "deposit_bonus"
    cashback = "cashback"
    promo_code = "promo_code"
    usdt = "usdt"
    fp = "fp"
    custom = "custom"


class Prize(Base, TimestampMixin):
    __tablename__ = "prizes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    prize_type: Mapped[PrizeType] = mapped_column(Enum(PrizeType), default=PrizeType.custom, nullable=False)
    value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_user_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    spins: Mapped[list["SpinHistory"]] = relationship(back_populates="prize", lazy="selectin")
