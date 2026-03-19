from pathlib import Path

from fastapi import HTTPException, Request, status
from fastapi.templating import Jinja2Templates

from app.db.session import AsyncSessionLocal


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


def require_admin(request: Request) -> str:
    admin_user = request.session.get("admin_user")
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/admin/login"},
        )
    return admin_user


def optional_admin(request: Request) -> str | None:
    return request.session.get("admin_user")
