import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import step_keyboard
from app.bot.services.content import get_funnel_steps, get_step_by_id, step_ids
from app.bot.services.funnel import render_step_text
from app.bot.services.single_message import send_single_message
from app.bot.states import FunnelStates
from app.db.models.spin import SpinHistory
from app.db.models.user import User
from app.db.session import AsyncSessionLocal


router = Router(name="webapp")


@router.message(F.web_app_data)
async def on_web_app_data(message: Message, state: FSMContext) -> None:
    if not message.web_app_data or not message.from_user:
        return

    try:
        payload = json.loads(message.web_app_data.data)
    except json.JSONDecodeError:
        await send_single_message(
            bot=message.bot,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            text="Failed to process spin result.",
        )
        return

    spin_id = payload.get("spin_id")
    won = bool(payload.get("won"))
    prize_name = payload.get("prize", "Bonus")
    reward_value = payload.get("reward_value", 0)

    step = None
    steps = []
    step_text = None
    keyboard = None
    async with AsyncSessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            return

        if spin_id:
            spin = await session.get(SpinHistory, spin_id)
            if spin and spin.user_id == user.id:
                spin.payload = {**(spin.payload or {}), "from_webapp": payload}

        if won:
            user.funnel_step = max(user.funnel_step, 8)
            steps = await get_funnel_steps(session)
            step = get_step_by_id(steps, user.funnel_step)
            step_text = render_step_text(user, step, steps)
            keyboard = await step_keyboard(session, user, step, step_ids(steps))

        await session.commit()

    await state.set_state(FunnelStates.in_funnel)

    if won:
        win_text = (
            f"🎉 Congratulations!\nYou won: {prize_name}\n"
            f"Credited: {reward_value}\n\n"
            "Continue the funnel to claim your next reward."
        )
        final_text = f"{win_text}\n\n{step_text}" if step_text else win_text
        if step:
            await send_single_message(
                bot=message.bot,
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                text=final_text,
                reply_markup=keyboard,
                photo=step.photo,
            )
        else:
            await send_single_message(
                bot=message.bot,
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                text=final_text,
            )
    else:
        await send_single_message(
            bot=message.bot,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            text=(
                "🤝 No win this time, but it is not over.\n"
                "Try again after cooldown and continue the funnel."
            ),
        )
