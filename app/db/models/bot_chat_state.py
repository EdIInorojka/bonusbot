from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BotChatState(Base, TimestampMixin):
    __tablename__ = "bot_chat_state"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    last_bot_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
