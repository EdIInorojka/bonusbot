import logging
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
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.admin.routers import auth, content, dashboard, exports, prizes, settings, users
from app.bot.handlers import router as bot_router
from app.bot.services.spins import SpinService, serialize_spin_result
from app.core.config import build_telegram_webhook_url, get_settings
from app.core.security import verify_telegram_init_data
from app.db.models.prize import Prize
from app.db.models.user import User
from app.db.seed import seed as seed_defaults
from app.db.session import AsyncSessionLocal, init_db


settings_obj = get_settings()
ADMIN_STATIC_DIR = Path(__file__).resolve().parent / "static"
WEBAPP_STATIC_DIR = Path(__file__).resolve().parents[1] / "webapp" / "static"
WEBAPP_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "webapp" / "templates"))



def _normalized_webhook_path() -> str:
    path = (settings_obj.telegram_webhook_path or "/api/telegram/webhook").strip()
    if not path.startswith("/"):
        path = "/" + path
    return path



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
    app.include_router(prizes.router)
    app.include_router(settings.router)
    app.include_router(content.router)
    app.include_router(users.router)
    app.include_router(exports.router)

    @app.on_event("startup")
    async def startup() -> None:
        try:
            await init_db()
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
