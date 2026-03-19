import html
from typing import Optional

from aiogram import Bot, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import step_keyboard
from app.bot.services.content import get_funnel_steps, get_links_config, get_step_by_id, step_ids
from app.bot.services.funnel import render_step_text
from app.bot.services.referrals import attach_referrer
from app.bot.services.single_message import send_single_message
from app.bot.services.users import get_or_create_user, get_user_by_ref_code
from app.bot.states import FunnelStates
from app.db.session import AsyncSessionLocal


router = Router(name="start")



def _extract_channel_slug(channel_url: str) -> str:
    value = channel_url.strip()
    if value.startswith("https://t.me/"):
        value = value.replace("https://t.me/", "", 1)
    if value.startswith("t.me/"):
        value = value.replace("t.me/", "", 1)
    return "@" + value.strip("/").lstrip("@")


async def is_subscribed(bot: Bot, user_id: int, channel_url: str) -> bool:
    try:
        member = await bot.get_chat_member(_extract_channel_slug(channel_url), user_id)
    except Exception:
        return True

    status = getattr(member, "status", None)
    if status in {"creator", "administrator", "member"}:
        return True
    return bool(status == "restricted" and getattr(member, "is_member", False))


async def _send_step_message(
    message: Message,
    session: AsyncSession,
    user_id: int,
    greeting: str | None = None,
) -> None:
    from app.db.models.user import User

    user = await session.get(User, user_id)
    if not user:
        return

    steps = await get_funnel_steps(session)
    step = get_step_by_id(steps, user.funnel_step)
    text = render_step_text(user, step, steps)
    if greeting:
        text = f"{text}\n\n{greeting}"

    keyboard = await step_keyboard(session, user, step, step_ids(steps))
    if step.photo:
        await send_single_message(
            bot=message.bot,
            user_id=user.id,
            chat_id=message.chat.id,
            text=text,
            reply_markup=keyboard,
            photo=step.photo,
        )
    else:
        await send_single_message(
            bot=message.bot,
            user_id=user.id,
            chat_id=message.chat.id,
            text=text,
            reply_markup=keyboard,
        )


async def _handle_start(message: Message, state: FSMContext, start_param: Optional[str]) -> None:
    if not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        user, created = await get_or_create_user(session, message.from_user)

        if created and start_param:
            referrer = await get_user_by_ref_code(session, start_param)
            await attach_referrer(session, user, referrer)

        links = await get_links_config(session)
        steps = await get_funnel_steps(session)
        first_step = steps[0]
        start_step = steps[1] if len(steps) > 1 else steps[0]

        subscribed = await is_subscribed(message.bot, user.id, links.get("channel", ""))
        if not subscribed:
            user.funnel_step = first_step.step
            await session.commit()
            await state.set_state(FunnelStates.waiting_subscription)
            await _send_step_message(message, session, user.id)
            return

        if user.funnel_step < start_step.step:
            user.funnel_step = start_step.step

        await session.commit()
        await state.set_state(FunnelStates.in_funnel)

        greeting = f"Hi, {html.escape(message.from_user.first_name or 'friend')}!"
        await _send_step_message(message, session, user.id, greeting=greeting)


@router.message(CommandStart(deep_link=True))
async def start_with_ref(message: Message, command: CommandObject, state: FSMContext) -> None:
    await _handle_start(message, state, command.args)


@router.message(CommandStart())
async def start_plain(message: Message, state: FSMContext) -> None:
    await _handle_start(message, state, None)
