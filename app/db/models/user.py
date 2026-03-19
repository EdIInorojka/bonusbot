import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.referral import Referral
    from app.db.models.spin import SpinHistory


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    ref_code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    referred_by_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    funnel_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_spins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(default=UserRole.user, nullable=False)

    referrals_from_me: Mapped[list["Referral"]] = relationship(
        back_populates="referrer",
        foreign_keys="Referral.referrer_id",
        lazy="selectin",
    )
    referrals_to_me: Mapped[list["Referral"]] = relationship(
        back_populates="referral",
        foreign_keys="Referral.referral_id",
        lazy="selectin",
    )

    spins: Mapped[list["SpinHistory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
