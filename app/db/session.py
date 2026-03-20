from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings, normalize_database_url_for_async
from app.db import models as _models  # noqa: F401
from app.db.base import Base


settings = get_settings()

engine: AsyncEngine = create_async_engine(
    normalize_database_url_for_async(settings.database_url),
    echo=False,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_user_conversion_columns() -> None:
    async with engine.begin() as conn:
        existing_columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("user_conversions")}
        )

        if "has_first_deposit" not in existing_columns:
            await conn.execute(
                text(
                    "ALTER TABLE user_conversions "
                    "ADD COLUMN has_first_deposit BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
        if "first_deposit_confirmed_at" not in existing_columns:
            await conn.execute(text("ALTER TABLE user_conversions ADD COLUMN first_deposit_confirmed_at TIMESTAMP"))
        if "first_deposit_amount" not in existing_columns:
            await conn.execute(text("ALTER TABLE user_conversions ADD COLUMN first_deposit_amount DOUBLE PRECISION"))
        if "bonus_claimed_at" not in existing_columns:
            await conn.execute(text("ALTER TABLE user_conversions ADD COLUMN bonus_claimed_at TIMESTAMP"))
