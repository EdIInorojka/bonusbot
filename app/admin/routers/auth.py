from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.admin.deps import optional_admin, templates
from app.core.config import get_settings


router = APIRouter(prefix="/admin", tags=["admin-auth"])


@router.get("/login")
async def login_page(request: Request):
    if optional_admin(request):
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    settings = get_settings()
    if username == settings.admin_username and password == settings.admin_password:
        request.session["admin_user"] = username
        return RedirectResponse(url="/admin", status_code=302)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": "Неверный логин или пароль"},
        status_code=400,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)
