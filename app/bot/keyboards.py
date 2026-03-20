from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services.content import DynamicFunnelStep, get_links_config
from app.bot.services.funnel import build_ref_link
from app.bot.services.registration import is_user_registered
from app.core.config import get_settings
from app.db.models.user import User


def _apply_user_placeholders(raw: str, user: User, links: dict[str, str]) -> str:
    ref_link = build_ref_link(user)
    values = {
        "{user_id}": str(user.id),
        "{source_id}": str(user.id),
        "{tg_id}": str(user.id),
        "{ref_code}": user.ref_code,
        "{ref_link}": ref_link,
        "{registration_url}": links.get("registration", ""),
    }
    rendered = raw
    for needle, replacement in values.items():
        rendered = rendered.replace(needle, replacement)
    return rendered


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


def _resolve_url(
    value: str,
    links: dict[str, str],
    user: User,
    registration_promo_param: str,
    registration_promo_code: str,
) -> str:
    raw_key = value.strip()
    raw = links.get(raw_key, raw_key)
    raw = _apply_user_placeholders(raw, user, links)

    if raw_key == "registration":
        raw = _append_query_param(raw, "sub1", str(user.id))
        raw = _append_query_param(raw, "source_id", str(user.id))
        raw = _append_query_param(raw, registration_promo_param, registration_promo_code)

    if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("t.me/"):
        return raw
    return raw


async def step_keyboard(
    session: AsyncSession,
    user: User,
    step: DynamicFunnelStep,
    _step_ids: list[int],
) -> InlineKeyboardMarkup:
    links = await get_links_config(session)
    settings = get_settings()
    promo_param = settings.registration_promo_param.strip()
    promo_code = settings.registration_promo_code.strip()

    buttons = step.buttons
    if step.slug == "main_menu":
        registered = await is_user_registered(session, user.id)
        if registered:
            preferred = tuple(
                btn
                for btn in step.buttons
                if btn.action == "callback" and btn.value in {"instruction", "claim_bonus"}
            )
            if preferred:
                buttons = preferred

    rows: list[list[InlineKeyboardButton]] = []

    for button in buttons:
        if button.action == "url":
            rows.append(
                [
                    InlineKeyboardButton(
                        text=button.text,
                        url=_resolve_url(button.value, links, user, promo_param, promo_code),
                    )
                ]
            )
        elif button.action == "webapp":
            webapp_url = _resolve_url(button.value, links, user, promo_param, promo_code)
            separator = "&" if "?" in webapp_url else "?"
            webapp_url = f"{webapp_url}{separator}startapp={user.ref_code}"
            rows.append([InlineKeyboardButton(text=button.text, web_app=WebAppInfo(url=webapp_url))])
        elif button.action == "callback":
            rows.append([InlineKeyboardButton(text=button.text, callback_data=f"funnel:{button.value}")])
        elif button.action == "next":
            rows.append([InlineKeyboardButton(text=button.text, callback_data=f"funnel:next:{button.value}")])
        elif button.action == "share":
            ref_link = build_ref_link(user)
            share_template = button.value.strip() if button.value.strip() else "Join and claim a bonus: {link}"
            share_text = quote_plus(share_template.replace("{link}", ref_link))
            rows.append(
                [
                    InlineKeyboardButton(
                        text=button.text,
                        url=f"https://t.me/share/url?url={quote_plus(ref_link)}&text={share_text}",
                    )
                ]
            )

    return InlineKeyboardMarkup(inline_keyboard=rows)
