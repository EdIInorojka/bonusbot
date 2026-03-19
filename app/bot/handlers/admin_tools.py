from aiogram import F, Router
from aiogram.types import Message

from app.bot.services.single_message import send_single_message
from app.core.config import get_settings


router = Router(name="admin-tools")


@router.message(F.photo)
async def admin_photo_file_id(message: Message) -> None:
    if not message.from_user or not message.photo:
        return

    settings = get_settings()
    if settings.admin_tg_id and message.from_user.id != settings.admin_tg_id:
        return

    file_id = message.photo[-1].file_id
    await send_single_message(
        bot=message.bot,
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        text=(
            "Use this file_id in admin panel (photo field):\n"
            f"<code>{file_id}</code>"
        ),
    )
