import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: str = Field(default="", alias="BOT_TOKEN")
    bot_username: str = Field(default="bonuskabot", alias="BOT_USERNAME")
    bot_mode: str = Field(default="polling", alias="BOT_MODE")
    database_url: str = Field(
        default="postgresql+asyncpg://bonuska:bonuska@postgres:5432/bonuska",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="", alias="REDIS_URL")

    web_base_url: str = Field(default="http://localhost:8000", alias="WEB_BASE_URL")
    webapp_path: str = Field(default="/webapp", alias="WEBAPP_PATH")
    webhook_base_url: str = Field(default="", alias="WEBHOOK_BASE_URL")
    telegram_webhook_path: str = Field(default="/api/telegram/webhook", alias="TELEGRAM_WEBHOOK_PATH")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    webhook_setup_token: str = Field(default="", alias="WEBHOOK_SETUP_TOKEN")

    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="admin", alias="ADMIN_PASSWORD")
    admin_session_secret: str = Field(default="change-me", alias="ADMIN_SESSION_SECRET")
    admin_tg_id: int = Field(default=0, alias="ADMIN_TG_ID")

    channel_url: str = Field(default="https://t.me/your_channel", alias="CHANNEL_URL")
    registration_url: str = Field(default="https://example.com/register", alias="REGISTRATION_URL")
    deposit_url: str = Field(default="https://example.com/deposit", alias="DEPOSIT_URL")
    instruction_url: str = Field(default="https://example.com/instruction", alias="INSTRUCTION_URL")
    bonus_claim_url: str = Field(default="https://example.com/bonus", alias="BONUS_CLAIM_URL")
    signal_url: str = Field(default="https://example.com/luckyjet-signal", alias="SIGNAL_URL")

    spin_cooldown_seconds: int = Field(default=300, alias="SPIN_COOLDOWN_SECONDS")
    max_daily_spins_per_user: int = Field(default=20, alias="MAX_DAILY_SPINS_PER_USER")
    global_win_rate: float = Field(default=0.35, alias="GLOBAL_WIN_RATE")

    default_referral_bonus_l1: float = Field(default=5.0, alias="REF_BONUS_L1")
    default_referral_bonus_l2: float = Field(default=4.0, alias="REF_BONUS_L2")
    default_referral_bonus_l3: float = Field(default=3.0, alias="REF_BONUS_L3")
    default_referral_bonus_l4: float = Field(default=2.0, alias="REF_BONUS_L4")
    default_referral_bonus_l5: float = Field(default=1.0, alias="REF_BONUS_L5")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def build_webapp_url() -> str:
    settings = get_settings()
    return f"{settings.web_base_url.rstrip('/')}{settings.webapp_path}"


def build_telegram_webhook_url() -> str:
    settings = get_settings()
    base = (settings.webhook_base_url or settings.web_base_url).strip()
    if not base:
        return ""

    path = settings.telegram_webhook_path.strip() or "/api/telegram/webhook"
    if not path.startswith("/"):
        path = "/" + path

    return f"{base.rstrip('/')}{path}"


def is_webhook_mode() -> bool:
    settings = get_settings()
    return settings.bot_mode.strip().lower() == "webhook"


def is_local_dev() -> bool:
    return os.getenv("ENV", "dev").lower() in {"dev", "local"}

