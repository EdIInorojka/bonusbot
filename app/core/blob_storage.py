from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from vercel.blob import AsyncBlobClient

from app.core.config import get_settings


_UNSAFE_FILENAME_CHARS = re.compile(r"[^a-zA-Z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    name = Path(filename or "").name.strip() or "image"
    name = _UNSAFE_FILENAME_CHARS.sub("_", name)
    return name[:120]


def blob_is_enabled() -> bool:
    settings = get_settings()
    return bool((settings.blob_read_write_token or "").strip())


def build_blob_path(filename: str) -> str:
    settings = get_settings()
    prefix = (settings.blob_prefix or "media").strip().strip("/")
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    safe_name = _sanitize_filename(filename)
    return f"{prefix}/{ts}-{safe_name}" if prefix else f"{ts}-{safe_name}"


async def upload_image_to_blob(filename: str, body: bytes, content_type: str) -> str:
    settings = get_settings()
    token = (settings.blob_read_write_token or "").strip()
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is not configured")

    client = AsyncBlobClient(token=token)
    result = await client.put(
        path=build_blob_path(filename),
        body=body,
        access="public",
        content_type=content_type,
        add_random_suffix=True,
        overwrite=False,
    )
    return result.url


async def delete_blob_object(url_or_path: str) -> None:
    settings = get_settings()
    token = (settings.blob_read_write_token or "").strip()
    if not token:
        return

    client = AsyncBlobClient(token=token)
    await client.delete(url_or_path)
