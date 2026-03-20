from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.handlers.start import is_subscribed
from app.bot.keyboards import step_keyboard
from app.bot.services.content import get_funnel_steps, get_links_config, get_step_by_id, get_step_by_slug, step_ids
from app.bot.services.funnel import next_step, prev_step, render_step_text
from app.bot.services.registration import can_claim_bonus_today, is_user_registered, mark_bonus_claimed
from app.bot.services.single_message import send_single_message
from app.bot.states import FunnelStates
from app.core.config import get_settings
from app.db.models.user import User
from app.db.session import AsyncSessionLocal


router = Router(name="funnel")


BONUS_STEP_SLUGS = ("bonus_claim", "bonus", "claim_bonus", "first_deposit")
REGISTRATION_ERROR_STEP_SLUGS = ("registration_error", "registration_check")


def _resolve_bonus_step_id(steps, fallback_id: int) -> int:
    for slug in BONUS_STEP_SLUGS:
        step = get_step_by_slug(steps, slug)
        if step:
            return step.step
    return fallback_id


def _resolve_registration_error_step_id(steps, fallback_id: int) -> int:
    for slug in REGISTRATION_ERROR_STEP_SLUGS:
        step = get_step_by_slug(steps, slug)
        if step:
            return step.step
    return fallback_id


def _append_query_param(url: str, key: str, value: str) -> str:
    if not key or not value:
        return url
    if not (url.startswith("http://") or url.startswith("https://")):
        return url

    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if key in params and str(params[key]).strip():
        return url
    params[key] = value
    query = urlencode(params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))


def _build_registration_url(raw_url: str, user: User | None) -> str:
    settings = get_settings()
    if not user:
        return raw_url

    url = raw_url
    url = url.replace("{user_id}", str(user.id))
    url = url.replace("{source_id}", str(user.id))
    url = url.replace("{tg_id}", str(user.id))
    url = _append_query_param(url, "sub1", str(user.id))
    url = _append_query_param(url, "source_id", str(user.id))
    url = _append_query_param(url, settings.registration_promo_param.strip(), settings.registration_promo_code.strip())
    return url


async def _resolve_claim_bonus_target(session, user_id: int, fallback_step: int) -> tuple[int, bool]:
    steps = await get_funnel_steps(session)
    main_menu_step = get_step_by_slug(steps, "main_menu") or get_step_by_id(steps, fallback_step)

    error_target = _resolve_registration_error_step_id(steps, fallback_step)
    bonus_target = _resolve_bonus_step_id(steps, next_step(main_menu_step.step, steps))

    registered = await is_user_registered(session, user_id)
    return (bonus_target if registered else error_target, registered)


def _render_instruction_text(template: str, user: User | None, links: dict[str, str]) -> str:
    if not template:
        return template

    user_id = str(user.id) if user else ""
    registration_url = _build_registration_url(links.get("registration", ""), user)
    result = template
    result = result.replace("{user_id}", user_id)
    result = result.replace("{source_id}", user_id)
    result = result.replace("{tg_id}", user_id)
    result = result.replace("{registration_url}", registration_url)
    return result


async def _send_current_step(bot: Bot, user_id: int, chat_id: int, step_id: int) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            return

        steps = await get_funnel_steps(session)
        step = get_step_by_id(steps, step_id)

        user.funnel_step = step.step
        await session.commit()

        text = render_step_text(user, step, steps)
        keyboard = await step_keyboard(session, user, step, step_ids(steps))

        await send_single_message(
            bot=bot,
            user_id=user.id,
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            photo=step.photo,
        )


@router.callback_query(F.data == "funnel:check_sub")
async def callback_check_sub(call: CallbackQuery, state: FSMContext) -> None:
    if not call.from_user or not call.message:
        return

    async with AsyncSessionLocal() as session:
        links = await get_links_config(session)
        steps = await get_funnel_steps(session)
        start_step = get_step_by_slug(steps, "main_menu") or (steps[1] if len(steps) > 1 else steps[0])

    ok = await is_subscribed(call.bot, call.from_user.id, links.get("channel", ""))
    if not ok:
        await call.answer("Subscription not found. Please subscribe and tap Check.", show_alert=True)
        return

    await state.set_state(FunnelStates.in_funnel)
    await _send_current_step(call.bot, call.from_user.id, call.message.chat.id, start_step.step)
    await call.answer("Great, subscription confirmed.")


@router.callback_query(F.data.startswith("funnel:next:"))
async def callback_next_fixed(call: CallbackQuery, state: FSMContext) -> None:
    if not call.from_user or not call.message:
        return

    parts = call.data.split(":")
    requested_target = int(parts[-1])
    answer_text = ""
    answer_alert = False

    async with AsyncSessionLocal() as session:
        user = await session.get(User, call.from_user.id)
        steps = await get_funnel_steps(session)
        main_menu_step = get_step_by_slug(steps, "main_menu")
        registration_error = get_step_by_slug(steps, "registration_error") or get_step_by_slug(steps, "registration_check")

        target = requested_target
        if user and main_menu_step and registration_error:
            if user.funnel_step == main_menu_step.step and requested_target == registration_error.step:
                target, registered = await _resolve_claim_bonus_target(session, user.id, requested_target)
                if not registered:
                    answer_text = "Complete registration first."
                    answer_alert = True

    await state.set_state(FunnelStates.in_funnel)
    await _send_current_step(call.bot, call.from_user.id, call.message.chat.id, target)
    await call.answer(answer_text, show_alert=answer_alert)


@router.callback_query(F.data == "funnel:claim_bonus")
async def callback_claim_bonus(call: CallbackQuery, state: FSMContext) -> None:
    if not call.from_user or not call.message:
        return

    registered = False
    can_claim_bonus = False
    target = 2
    async with AsyncSessionLocal() as session:
        user = await session.get(User, call.from_user.id)
        if not user:
            await call.answer()
            return

        steps = await get_funnel_steps(session)
        main_menu_step = get_step_by_slug(steps, "main_menu") or get_step_by_id(steps, user.funnel_step)
        target, registered = await _resolve_claim_bonus_target(session, user.id, user.funnel_step)
        if registered:
            can_claim_bonus = await can_claim_bonus_today(session, user.id)
            if can_claim_bonus:
                await mark_bonus_claimed(session, user.id, event_name="bonus_claim")
                await session.commit()
            else:
                target = main_menu_step.step

    await state.set_state(FunnelStates.in_funnel)
    await _send_current_step(call.bot, call.from_user.id, call.message.chat.id, target)
    if not registered:
        await call.answer("Registration callback not received yet.", show_alert=True)
        return

    if can_claim_bonus:
        await call.answer()
    else:
        await call.answer("Bonus is available once per day. Try again tomorrow.", show_alert=True)


@router.callback_query(F.data == "funnel:continue")
async def callback_continue(call: CallbackQuery) -> None:
    if not call.from_user or not call.message:
        return

    async with AsyncSessionLocal() as session:
        user = await session.get(User, call.from_user.id)
        if not user:
            await call.answer()
            return
        steps = await get_funnel_steps(session)
        target = next_step(user.funnel_step, steps)

    await _send_current_step(call.bot, call.from_user.id, call.message.chat.id, target)
    await call.answer()


@router.callback_query(F.data == "funnel:back")
async def callback_back(call: CallbackQuery) -> None:
    if not call.from_user or not call.message:
        return

    async with AsyncSessionLocal() as session:
        user = await session.get(User, call.from_user.id)
        if not user:
            await call.answer()
            return
        steps = await get_funnel_steps(session)
        target = prev_step(user.funnel_step, steps)

    await _send_current_step(call.bot, call.from_user.id, call.message.chat.id, target)
    await call.answer()


@router.callback_query(F.data == "funnel:lang")
async def callback_lang(call: CallbackQuery) -> None:
    await call.answer("Language switch is disabled.", show_alert=True)


@router.callback_query(F.data == "funnel:instruction")
async def callback_instruction(call: CallbackQuery) -> None:
    if not call.from_user or not call.message:
        return

    async with AsyncSessionLocal() as session:
        links = await get_links_config(session)
        user = await session.get(User, call.from_user.id)
        back_step = user.funnel_step if user else 2

    instruction_text = links.get("instruction_message", "").strip()
    if not instruction_text:
        instruction_text = "📘 <b>How to use the bot</b>\n\n1) Register.\n2) Deposit.\n3) Follow funnel steps."
    instruction_text = _render_instruction_text(instruction_text, user, links)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="< Back", callback_data=f"funnel:next:{back_step}")]
        ]
    )
    await send_single_message(
        bot=call.bot,
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        text=instruction_text,
        reply_markup=keyboard,
    )
    await call.answer()
