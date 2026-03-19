import enum

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MediaAssetType(str, enum.Enum):
    file_id = "file_id"
    url = "url"


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False, default="image")
    asset_type: Mapped[MediaAssetType] = mapped_column(
        Enum(MediaAssetType),
        nullable=False,
        default=MediaAssetType.file_id,
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
