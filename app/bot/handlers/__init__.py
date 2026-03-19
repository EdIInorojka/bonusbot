from aiogram import Router

from app.bot.handlers import admin_tools, funnel, start, webapp

router = Router()
router.include_router(start.router)
router.include_router(funnel.router)
router.include_router(webapp.router)
router.include_router(admin_tools.router)
