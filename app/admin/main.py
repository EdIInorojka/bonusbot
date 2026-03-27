import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, Update
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis
from sqlalchemy import or_, select
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.admin.routers import auth, content, dashboard, media, settings
from app.bot.content_defaults import DEFAULT_FUNNEL_STEPS, DEFAULT_LINKS
from app.bot.handlers import router as bot_router
from app.bot.keyboards import step_keyboard
from app.bot.services.content import get_funnel_steps, get_step_by_slug, step_ids
from app.bot.services.funnel import render_step_text
from app.bot.services.registration import (
    extract_event_name,
    extract_amount,
    extract_source_user_id,
    is_first_deposit_event,
    is_registration_event,
    mark_first_deposit,
    mark_user_registered,
)
from app.bot.services.single_message import send_single_message
from app.bot.services.spins import SpinService, serialize_spin_result
from app.core.config import build_telegram_webhook_url, build_webapp_url, get_settings
from app.core.security import verify_telegram_init_data
from app.db.models.bot_chat_state import BotChatState
from app.db.models.prize import Prize
from app.db.models.user import User
from app.db.models.admin_settings import AdminSettings
from app.db.models.user_conversion import UserConversion
from app.db.seed import seed as seed_defaults
from app.db.session import AsyncSessionLocal, ensure_user_conversion_columns, init_db


settings_obj = get_settings()
ADMIN_STATIC_DIR = Path(__file__).resolve().parent / "static"
WEBAPP_STATIC_DIR = Path(__file__).resolve().parents[1] / "webapp" / "static"
WEBAPP_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "webapp" / "templates"))
POSTBACK_BONUS_STEP_SLUGS = ("bonus_claim", "bonus", "claim_bonus", "first_deposit")



def _normalized_webhook_path() -> str:
    path = (settings_obj.telegram_webhook_path or "/api/telegram/webhook").strip()
    if not path.startswith("/"):
        path = "/" + path
    return path


def _normalized_postback_path() -> str:
    path = (settings_obj.postback_path or "/api/postback/event").strip()
    if not path.startswith("/"):
        path = "/" + path
    return path


async def _extract_postback_payload(request: Request) -> dict[str, str]:
    payload: dict[str, str] = {str(k): str(v) for k, v in request.query_params.multi_items()}

    if request.method.upper() != "POST":
        return payload

    content_type = (request.headers.get("content-type") or "").lower()
    try:
        if "application/json" in content_type:
            raw_json = await request.json()
            if isinstance(raw_json, dict):
                payload.update({str(k): str(v) for k, v in raw_json.items()})
            return payload

        form = await request.form()
        payload.update({str(k): str(v) for k, v in form.multi_items()})
        return payload
    except Exception:
        return payload


def _validate_postback_secret(request: Request, payload: dict[str, str]) -> None:
    expected = (settings_obj.postback_secret or "").strip()
    if not expected:
        return

    provided = (
        request.headers.get("x-postback-secret", "").strip()
        or request.query_params.get("secret", "").strip()
        or request.query_params.get("token", "").strip()
        or str(payload.get("secret", "")).strip()
        or str(payload.get("token", "")).strip()
    )
    if provided != expected:
        raise HTTPException(status_code=403, detail="Invalid postback secret")


def _resolve_postback_bonus_step(steps):
    for slug in POSTBACK_BONUS_STEP_SLUGS:
        step = get_step_by_slug(steps, slug)
        if step:
            return step

    return get_step_by_slug(steps, "main_menu") or steps[0]


def _extract_int(payload: dict[str, str], key: str) -> int | None:
    raw = str(payload.get(key, "")).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def _resolve_postback_user_id(
    session,
    payload: dict[str, str],
    extracted_source_id: int | None,
) -> tuple[int | None, str]:
    if extracted_source_id is not None:
        direct_user = await session.get(User, extracted_source_id)
        if direct_user:
            return direct_user.id, "direct"

    preferred_keys = ("sub1", "sub_id", "subid", "source", "s1", "tg_id", "telegram_id", "user_id", "userid", "uid")
    for key in preferred_keys:
        candidate = _extract_int(payload, key)
        if candidate is None:
            continue
        user = await session.get(User, candidate)
        if user:
            return user.id, f"payload:{key}"

    # Resolve via historical payload mapping when tracker sends external account id.
    if extracted_source_id is not None:
        src = str(extracted_source_id)
        source_patterns = [
            f"\"source_id\": \"{src}\"",
            f"\"source_id\":\"{src}\"",
            f"\"user_id\": \"{src}\"",
            f"\"user_id\":\"{src}\"",
        ]
        payload_match_rows = (
            await session.execute(
                select(UserConversion.user_id)
                .where(
                    or_(
                        *[
                            UserConversion.payload_json.like(f"%{pattern}%")
                            for pattern in source_patterns
                        ]
                    )
                )
                .order_by(UserConversion.updated_at.desc())
                .limit(2)
            )
        ).scalars().all()
        if len(payload_match_rows) == 1:
            return payload_match_rows[0], "payload_history:source_id"

    # Fallback for trackers that only send external account id in source_id.
    # We map only when there is exactly one recent unresolved Telegram user.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    unresolved_rows = (
        await session.execute(
            select(User.id)
            .join(BotChatState, BotChatState.user_id == User.id)
            .outerjoin(UserConversion, UserConversion.user_id == User.id)
            .where(
                User.created_at >= cutoff,
                or_(UserConversion.user_id.is_(None), UserConversion.is_registered.is_(False)),
            )
            .order_by(BotChatState.updated_at.desc(), User.created_at.desc())
            .limit(2)
        )
    ).scalars().all()

    if len(unresolved_rows) == 1:
        return unresolved_rows[0], "fallback:recent_single_unresolved"

    return None, "unresolved"



def _validate_setup_token(request: Request, setup_token: str | None) -> None:
    expected = (settings_obj.webhook_setup_token or "").strip()
    if not expected:
        return

    provided = (
        (setup_token or "").strip()
        or request.query_params.get("setup_token", "").strip()
        or request.headers.get("x-setup-token", "").strip()
    )

    if provided != expected:
        raise HTTPException(status_code=403, detail="Invalid setup token")



def create_app() -> FastAPI:
    app = FastAPI(title="Bonuska Admin")
    app.add_middleware(SessionMiddleware, secret_key=settings_obj.admin_session_secret)

    app.mount("/admin/static", StaticFiles(directory=str(ADMIN_STATIC_DIR)), name="admin_static")
    app.mount("/webapp/static", StaticFiles(directory=str(WEBAPP_STATIC_DIR)), name="webapp_static")

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(settings.router)
    app.include_router(content.router)
    app.include_router(media.router)

    @app.on_event("startup")
    async def startup() -> None:
        try:
            await init_db()
            await ensure_user_conversion_columns()
            await seed_defaults()
        except Exception:
            logging.exception("Failed to initialize database")

        app.state.redis = None
        app.state.bot = None
        app.state.dp = None
        app.state.fsm_storage = None

        redis_url = (settings_obj.redis_url or "").strip()
        if redis_url:
            try:
                redis = Redis.from_url(redis_url, decode_responses=True)
                await redis.ping()
                app.state.redis = redis
            except Exception:
                logging.exception("Failed to initialize Redis, fallback to in-memory storage")

        if settings_obj.bot_token:
            try:
                bot = Bot(
                    token=settings_obj.bot_token,
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                )
                storage = RedisStorage(redis=app.state.redis) if app.state.redis else MemoryStorage()
                dp = Dispatcher(storage=storage)
                dp.include_router(bot_router)

                app.state.bot = bot
                app.state.dp = dp
                app.state.fsm_storage = storage
            except Exception:
                logging.exception("Failed to initialize Telegram bot runtime")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        storage = app.state.fsm_storage
        if storage:
            await storage.close()

        bot: Bot | None = app.state.bot
        if bot:
            await bot.session.close()

        redis: Redis | None = app.state.redis
        if redis:
            await redis.aclose()

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/admin", status_code=302)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/content/apply-defaults")
    async def apply_content_defaults(request: Request, setup_token: str | None = Form(default=None)):
        _validate_setup_token(request, setup_token)

        default_links = dict(DEFAULT_LINKS)
        default_links.update(
            {
                "channel": settings_obj.channel_url,
                "registration": settings_obj.registration_url,
                "deposit": settings_obj.deposit_url,
                "instruction": settings_obj.instruction_url,
                "instruction_message": settings_obj.instruction_message,
                "bonus": settings_obj.bonus_claim_url,
                "signal": settings_obj.signal_url,
                "webapp": build_webapp_url(),
                "mines_webapp": build_webapp_url("/mines"),
            }
        )

        async with AsyncSessionLocal() as session:
            links_row = await session.get(AdminSettings, "links_json")
            steps_row = await session.get(AdminSettings, "funnel_steps_json")

            links_payload = json.dumps(default_links, ensure_ascii=False)
            steps_payload = json.dumps(DEFAULT_FUNNEL_STEPS, ensure_ascii=False)

            if not links_row:
                links_row = AdminSettings(key="links_json", value=links_payload)
                session.add(links_row)
            else:
                links_row.value = links_payload

            if not steps_row:
                steps_row = AdminSettings(key="funnel_steps_json", value=steps_payload)
                session.add(steps_row)
            else:
                steps_row.value = steps_payload

            await session.commit()

        return {"ok": True}

    async def _handle_postback(
        request: Request,
        force_registration: bool = False,
        force_first_deposit: bool = False,
    ):
        payload = await _extract_postback_payload(request)
        _validate_postback_secret(request, payload)

        event_name = extract_event_name(payload)
        extracted_source_id = extract_source_user_id(payload)

        registration_event = force_registration or is_registration_event(event_name)
        first_deposit_event = force_first_deposit or is_first_deposit_event(event_name)
        deposit_amount = extract_amount(payload)

        sent_to_user = False
        target_step_id: int | None = None
        resolved_user_id: int | None = None
        mapping_strategy = "unresolved"
        async with AsyncSessionLocal() as session:
            resolved_user_id, mapping_strategy = await _resolve_postback_user_id(
                session=session,
                payload=payload,
                extracted_source_id=extracted_source_id,
            )
            if resolved_user_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cannot map postback to Telegram user. "
                        "Send sub1/source_id with Telegram user id in postback URL."
                    ),
                )

            user = await session.get(User, resolved_user_id)
            if not user:
                raise HTTPException(status_code=400, detail="Target Telegram user not found")

            if registration_event:
                await mark_user_registered(session, user.id, event_name or "registration", payload)
                steps = await get_funnel_steps(session)
                target_step = _resolve_postback_bonus_step(steps)
                user.funnel_step = max(user.funnel_step, target_step.step)
                target_step_id = target_step.step

                chat_state = await session.get(BotChatState, user.id)
                bot: Bot | None = app.state.bot
                if chat_state and bot:
                    text = render_step_text(user, target_step, steps)
                    keyboard = await step_keyboard(session, user, target_step, step_ids(steps))
                    await send_single_message(
                        bot=bot,
                        user_id=user.id,
                        chat_id=chat_state.chat_id,
                        text=text,
                        reply_markup=keyboard,
                        photo=target_step.photo,
                    )
                    sent_to_user = True

            if first_deposit_event:
                await mark_first_deposit(session, user.id, event_name or "first_deposit", payload)

            await session.commit()

        return {
            "ok": True,
            "registration_event": registration_event,
            "first_deposit_event": first_deposit_event,
            "first_deposit_amount": deposit_amount,
            "source_user_id": extracted_source_id,
            "resolved_user_id": resolved_user_id,
            "mapping_strategy": mapping_strategy,
            "event_name": event_name,
            "target_step": target_step_id,
            "sent_to_user": sent_to_user,
        }

    @app.api_route(_normalized_postback_path(), methods=["GET", "POST"])
    async def postback_event(request: Request):
        return await _handle_postback(request, force_registration=False, force_first_deposit=False)

    @app.api_route("/api/postback/registration", methods=["GET", "POST"])
    async def postback_registration(request: Request):
        return await _handle_postback(request, force_registration=True, force_first_deposit=False)

    @app.api_route("/api/postback/first-deposit", methods=["GET", "POST"])
    async def postback_first_deposit(request: Request):
        return await _handle_postback(request, force_registration=False, force_first_deposit=True)

    @app.post(_normalized_webhook_path())
    async def telegram_webhook(request: Request):
        bot: Bot | None = app.state.bot
        dp: Dispatcher | None = app.state.dp
        if not bot or not dp:
            raise HTTPException(status_code=503, detail="Bot runtime is not initialized")

        expected_secret = (settings_obj.telegram_webhook_secret or "").strip()
        if expected_secret:
            got_secret = request.headers.get("x-telegram-bot-api-secret-token", "").strip()
            if got_secret != expected_secret:
                raise HTTPException(status_code=403, detail="Invalid webhook secret")

        payload = await request.json()
        update = Update.model_validate(payload)
        await dp.feed_update(bot, update)
        return {"ok": True}

    @app.post("/api/telegram/set-webhook")
    async def set_telegram_webhook(request: Request, setup_token: str | None = Form(default=None)):
        _validate_setup_token(request, setup_token)

        bot: Bot | None = app.state.bot
        if not bot:
            raise HTTPException(status_code=503, detail="Bot runtime is not initialized")

        webhook_url = build_telegram_webhook_url()
        if not webhook_url:
            raise HTTPException(status_code=400, detail="WEBHOOK_BASE_URL is not configured")

        await bot.set_webhook(
            url=webhook_url,
            secret_token=(settings_obj.telegram_webhook_secret or None),
            drop_pending_updates=True,
        )
        return {"ok": True, "webhook_url": webhook_url}

    @app.get("/api/telegram/webhook-info")
    async def get_telegram_webhook_info(request: Request, setup_token: str | None = None):
        _validate_setup_token(request, setup_token)

        bot: Bot | None = app.state.bot
        if not bot:
            raise HTTPException(status_code=503, detail="Bot runtime is not initialized")

        info = await bot.get_webhook_info()
        return info.model_dump(mode="json")

    @app.get("/webapp")
    async def webapp_page(request: Request):
        return WEBAPP_TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "bot_username": settings_obj.bot_username,
            },
        )

    @app.get("/webapp/mines")
    async def mines_webapp_page(request: Request):
        return WEBAPP_TEMPLATES.TemplateResponse(
            request,
            "mines.html",
            {
                "request": request,
                "bot_username": settings_obj.bot_username,
            },
        )

    @app.get("/webapp/api/config")
    async def webapp_config():
        async with AsyncSessionLocal() as session:
            prizes_rows = (await session.execute(select(Prize).where(Prize.is_active.is_(True)))).scalars().all()

        total_prizes = [p.display_text for p in prizes_rows] or ["+5 spins", "+500% deposit bonus", "BONUS 32,000₽"]
        return {
            "attempts": 8,
            "button_text": "PLAY",
            "prizes": total_prizes,
            "symbols": ["🍉", "🍒", "🔔", "🎁", "🍋", "7"],
        }

    @app.post("/webapp/api/spin")
    async def webapp_spin(
        request: Request,
        init_data: str = Form(...),
        session_key: str = Form(default=""),
    ):
        try:
            validated = verify_telegram_init_data(init_data, settings_obj.bot_token)
            tg_user = validated.get("user") or {}
            tg_id = int(tg_user["id"])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
        user_agent = request.headers.get("user-agent")

        redis: Redis | None = request.app.state.redis
        spin_service = SpinService(redis)

        async with AsyncSessionLocal() as session:
            user = await session.get(User, tg_id)
            if not user:
                user = User(
                    id=tg_id,
                    first_name=tg_user.get("first_name", "User"),
                    last_name=tg_user.get("last_name"),
                    username=tg_user.get("username"),
                    language_code=tg_user.get("language_code"),
                    ref_code=f"REF{tg_id}",
                    funnel_step=2,
                )
                session.add(user)
                await session.flush()

            cooldown_left = await spin_service.cooldown_left(user.id, ip)
            if cooldown_left > 0:
                return JSONResponse(status_code=429, content={"detail": f"Wait {cooldown_left} sec."})

            prize = await spin_service.choose_prize(session, user.id)
            spin = await spin_service.save_spin(
                session,
                user=user,
                prize=prize,
                ip=ip,
                user_agent=user_agent,
                session_key=session_key,
                payload={"source": "webapp"},
            )
            await session.commit()

            payload_to_bot = serialize_spin_result(spin, prize)
            return {
                "spin_id": spin.id,
                "won": bool(prize),
                "prize": prize.display_text if prize else "No win",
                "reward_value": prize.value if prize else 0,
                "cooldown_seconds": await spin_service.get_cooldown(session),
                "payload_to_bot": payload_to_bot,
            }

    @app.post("/webapp/api/answer-web-query")
    async def answer_web_query(
        web_app_query_id: str = Form(...),
        text: str = Form(...),
    ):
        bot: Bot | None = app.state.bot
        if not bot:
            raise HTTPException(status_code=400, detail="BOT_TOKEN is not configured")
        try:
            await bot.answer_web_app_query(
                web_app_query_id=web_app_query_id,
                result=InlineQueryResultArticle(
                    id=web_app_query_id,
                    title="Result",
                    input_message_content=InputTextMessageContent(message_text=text),
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    return app


app = create_app()
