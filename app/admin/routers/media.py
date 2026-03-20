import base64
from urllib.parse import quote_plus

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.core.blob_storage import blob_is_enabled, delete_blob_object, upload_image_to_blob
from app.core.config import get_settings
from app.db.models.media_asset import MediaAsset, MediaAssetType


router = APIRouter(prefix="/admin/media", tags=["admin-media"])


@router.get("")
async def media_page(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    assets = (
        await session.execute(select(MediaAsset).order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc()))
    ).scalars().all()
    return templates.TemplateResponse(
        request,
        "media.html",
        {
            "request": request,
            "assets": assets,
            "blob_enabled": blob_is_enabled(),
            "msg": request.query_params.get("msg", ""),
            "error": request.query_params.get("error", ""),
        },
    )


@router.post("/upload")
async def upload_media_file(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
    label: str = Form(default=""),
    image: UploadFile = File(...),
):
    if not image.filename:
        return RedirectResponse(url="/admin/media?error=Файл+не+выбран", status_code=302)

    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        return RedirectResponse(url="/admin/media?error=Можно+загружать+только+изображения", status_code=302)

    data = await image.read()
    if not data:
        return RedirectResponse(url="/admin/media?error=Файл+пустой", status_code=302)
    if len(data) > 10 * 1024 * 1024:
        return RedirectResponse(url="/admin/media?error=Файл+слишком+большой+(максимум+10MB)", status_code=302)

    preview = (
        f"data:{content_type};base64,{base64.b64encode(data).decode('ascii')}"
        if len(data) <= 1_500_000
        else None
    )

    asset: MediaAsset
    if blob_is_enabled():
        try:
            blob_url = await upload_image_to_blob(
                filename=image.filename,
                body=data,
                content_type=content_type,
            )
        except Exception:
            return RedirectResponse(url="/admin/media?error=Не+удалось+загрузить+в+Vercel+Blob", status_code=302)

        asset = MediaAsset(
            label=label.strip() or image.filename,
            asset_type=MediaAssetType.url,
            value=blob_url,
            preview_url=blob_url,
        )
        success_message = "Изображение загружено в Blob"
    else:
        bot = request.app.state.bot
        settings = get_settings()
        if not bot:
            return RedirectResponse(
                url="/admin/media?error=BOT_TOKEN+не+настроен,+а+Blob+token+не+задан",
                status_code=302,
            )
        if not settings.admin_tg_id:
            return RedirectResponse(url="/admin/media?error=ADMIN_TG_ID+не+настроен", status_code=302)

        sent = await bot.send_photo(
            chat_id=settings.admin_tg_id,
            photo=BufferedInputFile(data, filename=image.filename),
            caption="media_upload",
        )
        file_id = sent.photo[-1].file_id if sent.photo else ""
        if not file_id:
            return RedirectResponse(url="/admin/media?error=Не+удалось+получить+file_id", status_code=302)

        try:
            await bot.delete_message(chat_id=settings.admin_tg_id, message_id=sent.message_id)
        except Exception:
            pass

        asset = MediaAsset(
            label=label.strip() or image.filename,
            asset_type=MediaAssetType.file_id,
            value=file_id,
            preview_url=preview,
        )
        success_message = "Изображение загружено в Telegram"

    session.add(asset)
    await session.commit()

    return RedirectResponse(url=f"/admin/media?msg={quote_plus(success_message)}", status_code=302)


@router.post("/add-url")
async def add_media_url(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
    label: str = Form(default=""),
    url: str = Form(...),
):
    value = url.strip()
    if not value:
        return RedirectResponse(url="/admin/media?error=URL+пустой", status_code=302)

    asset = MediaAsset(
        label=label.strip() or "url-image",
        asset_type=MediaAssetType.url,
        value=value,
        preview_url=value,
    )
    session.add(asset)
    await session.commit()
    return RedirectResponse(url="/admin/media?msg=URL+добавлен", status_code=302)


@router.post("/add-file-id")
async def add_media_file_id(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
    label: str = Form(default=""),
    file_id: str = Form(...),
):
    value = file_id.strip()
    if not value:
        return RedirectResponse(url="/admin/media?error=file_id+пустой", status_code=302)

    asset = MediaAsset(
        label=label.strip() or "telegram-file-id",
        asset_type=MediaAssetType.file_id,
        value=value,
        preview_url=None,
    )
    session.add(asset)
    await session.commit()
    return RedirectResponse(url="/admin/media?msg=file_id+добавлен", status_code=302)


@router.post("/{asset_id}/delete")
async def delete_media_asset(
    asset_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    asset = await session.get(MediaAsset, asset_id)
    if not asset:
        return RedirectResponse(
            url=f"/admin/media?error={quote_plus('Элемент не найден')}",
            status_code=302,
        )

    if asset.asset_type == MediaAssetType.url:
        try:
            await delete_blob_object(asset.value)
        except Exception:
            pass

    await session.delete(asset)
    await session.commit()
    return RedirectResponse(url="/admin/media?msg=Элемент+удален", status_code=302)
