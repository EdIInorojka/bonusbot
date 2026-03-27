import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    blob_read_write_token: str = Field(default="", alias="BLOB_READ_WRITE_TOKEN")
    blob_prefix: str = Field(default="media", alias="BLOB_PREFIX")

    web_base_url: str = Field(default="http://localhost:8000", alias="WEB_BASE_URL")
    webapp_path: str = Field(default="/webapp", alias="WEBAPP_PATH")
    webhook_base_url: str = Field(default="", alias="WEBHOOK_BASE_URL")
    telegram_webhook_path: str = Field(default="/api/telegram/webhook", alias="TELEGRAM_WEBHOOK_PATH")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    webhook_setup_token: str = Field(default="", alias="WEBHOOK_SETUP_TOKEN")
    postback_path: str = Field(default="/api/postback/event", alias="POSTBACK_PATH")
    postback_secret: str = Field(default="", alias="POSTBACK_SECRET")

    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="admin", alias="ADMIN_PASSWORD")
    admin_session_secret: str = Field(default="change-me", alias="ADMIN_SESSION_SECRET")
    admin_tg_id: int = Field(default=0, alias="ADMIN_TG_ID")

    channel_url: str = Field(default="https://t.me/your_channel", alias="CHANNEL_URL")
    registration_url: str = Field(
        default="https://1wcous.life/casino/list?open=register&sub1={source_id}",
        alias="REGISTRATION_URL",
    )
    registration_promo_code: str = Field(default="HUNTCASH", alias="REGISTRATION_PROMO_CODE")
    registration_promo_param: str = Field(default="promocode", alias="REGISTRATION_PROMO_PARAM")
    deposit_url: str = Field(default="https://example.com/deposit", alias="DEPOSIT_URL")
    instruction_url: str = Field(default="https://example.com/instruction", alias="INSTRUCTION_URL")
    instruction_message: str = Field(
        default=(
            "🤖<b>Бот основан и обучен на кластерной нейронной сети OpenAI!</b>\n"
            "⚜️Для обучения бота было сыграно 🎰30,000 игр.\n\n"
            "В настоящее время пользователи бота успешно генерируют 15-25% от своего капитала ежедневно!\n\n"
            "Бот все еще проходит проверки и исправления! Точность бота составляет 92%!\n"
            "Чтобы достичь максимальной прибыли, следуйте этой инструкции:\n\n"
            "🟢 1. Зарегистрируйтесь в букмекерской конторе 1WIN: "
            "<a href=\"{registration_url}\">1WIN</a>\n"
            "[Если не открывается, воспользуйтесь VPN (Швеция).]\n"
            "❗️Без регистрации и промокода доступ к сигналам не будет открыт❗️\n\n"
            "🟢 2. Пополните баланс своего счета.\n"
            "🟢 3. Перейдите в раздел игр 1win и выберите игру.\n"
            "🟢 4. Установите количество ловушек на три. Это важно!\n"
            "🟢 5. Запросите сигнал у бота и ставьте ставки в соответствии с сигналами от бота.\n"
            "🟢 6. В случае неудачного сигнала рекомендуем удвоить (x²) вашу ставку."
        ),
        alias="INSTRUCTION_MESSAGE",
    )
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


def build_webapp_url(path_suffix: str | None = None) -> str:
    settings = get_settings()
    base_url = f"{settings.web_base_url.rstrip('/')}{settings.webapp_path}"
    suffix = (path_suffix or "").strip()
    if not suffix:
        return base_url
    if not suffix.startswith("/"):
        suffix = "/" + suffix
    return f"{base_url.rstrip('/')}{suffix}"


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


def normalize_database_url_for_async(database_url: str | None = None) -> str:
    settings = get_settings()
    db_url = (database_url or settings.database_url or "").strip()
    if not db_url:
        return db_url

    lower = db_url.lower()
    if lower.startswith("postgres://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgres://") :]
    elif lower.startswith("postgresql://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql://") :]

    if not db_url.lower().startswith("postgresql+asyncpg://"):
        return db_url

    split = urlsplit(db_url)
    if not split.query:
        return db_url

    blocked_keys = {"channel_binding", "sslmode"}
    safe_query = [(k, v) for k, v in parse_qsl(split.query, keep_blank_values=True) if k not in blocked_keys]
    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(safe_query, doseq=True),
            split.fragment,
        )
    )


def is_ephemeral_database_url(database_url: str | None = None) -> bool:
    settings = get_settings()
    db_url = (database_url or settings.database_url or "").strip().lower()
    if not db_url:
        return True

    if db_url.startswith("sqlite"):
        return ("/tmp/" in db_url) or (":memory:" in db_url)

    return False


def mask_database_url(database_url: str | None = None) -> str:
    settings = get_settings()
    db_url = (database_url or settings.database_url or "").strip()
    if not db_url:
        return "not-configured"

    if "://" not in db_url:
        return db_url

    scheme, rest = db_url.split("://", 1)
    if "@" not in rest:
        return f"{scheme}://{rest}"

    _, host_part = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host_part}"

