import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message

from app.db.models.bot_chat_state import BotChatState
from app.db.session import AsyncSessionLocal


async def send_single_message(
    bot: Bot,
    user_id: int,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    photo: str | None = None,
) -> Message:
    async with AsyncSessionLocal() as session:
        state = await session.get(BotChatState, user_id)

        if state and state.last_bot_message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=state.last_bot_message_id)
            except Exception:
                logging.debug("Could not delete previous bot message", exc_info=True)

        if photo:
            caption = text if len(text) <= 1024 else text[:1021] + "..."
            sent = await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
            )
        else:
            sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

        if not state:
            state = BotChatState(
                user_id=user_id,
                chat_id=chat_id,
                last_bot_message_id=sent.message_id,
            )
            session.add(state)
        else:
            state.chat_id = chat_id
            state.last_bot_message_id = sent.message_id

        await session.commit()
        return sent
