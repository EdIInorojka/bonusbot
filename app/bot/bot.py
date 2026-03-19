import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.handlers import router as root_router
from app.core.config import get_settings, is_webhook_mode
from app.core.logging import setup_logging


async def main() -> None:
    setup_logging()
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not configured")
    if is_webhook_mode():
        logging.info("BOT_MODE=webhook, polling process skipped")
        return

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    storage = MemoryStorage()
    redis = None
    redis_url = (settings.redis_url or "").strip()
    if redis_url:
        try:
            redis = Redis.from_url(redis_url, decode_responses=True)
            await redis.ping()
            storage = RedisStorage(redis=redis)
        except Exception:
            logging.exception("Failed to initialize Redis storage, fallback to MemoryStorage")

    dp = Dispatcher(storage=storage)
    dp.include_router(root_router)

    logging.info("Starting bot polling")
    try:
        await dp.start_polling(bot)
    finally:
        await storage.close()
        if redis:
            await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())