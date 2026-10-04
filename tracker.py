"""
Встроенный HTTP-трекер.

Эндпоинты:
  GET  /ref/{slug}          — фиксирует клик, редиректит на лендинг
  POST /lead/{slug}         — фиксирует лид, уведомляет воркера
  GET  /health              — проверка работоспособности

Запускается в том же процессе что и бот через asyncio.gather.
"""

import logging
from aiohttp import web

from db.database import async_session
from db.models import Link, Landing, Stat
from sqlalchemy import select

logger = logging.getLogger(__name__)


def create_tracker_app(bot) -> web.Application:
    """Создаёт aiohttp приложение и пробрасывает bot для уведомлений."""
    app = web.Application()
    app["bot"] = bot

    app.router.add_get("/ref/{slug}",    handle_click)
    app.router.add_post("/lead/{slug}",  handle_lead)
    app.router.add_get("/health",        handle_health)

    return app


# ──────────────────────────────────────────────
# GET /ref/{slug} — клик
# ──────────────────────────────────────────────
async def handle_click(request: web.Request) -> web.Response:
    slug = request.match_info["slug"]
    ip   = request.headers.get("X-Forwarded-For", request.remote)

    async with async_session() as session:
        link = await session.scalar(select(Link).where(Link.slug == slug))

        if not link or not link.is_active:
            raise web.HTTPNotFound(text="Link not found")

        # Записываем клик
        stat = Stat(link_id=link.id, event="click", meta=ip)
        session.add(stat)

        # Ищем URL редиректа
        redirect_url = None
        if link.landing_id:
            landing = await session.get(Landing, link.landing_id)
            if landing and landing.url:
                redirect_url = landing.url

        await session.commit()

    if redirect_url:
        raise web.HTTPFound(location=redirect_url)
    else:
        # Лендинг ещё не привязан — возвращаем заглушку
        return web.Response(
            text="<h2>Coming soon</h2>",
            content_type="text/html",
            status=200,
        )


# ──────────────────────────────────────────────
# POST /lead/{slug} — лид
# ──────────────────────────────────────────────
async def handle_lead(request: web.Request) -> web.Response:
    """
    Лендинг отправляет POST на этот эндпоинт когда пользователь оставил заявку.
    Тело запроса (JSON, опционально):
      { "meta": "any string info about lead" }
    """
    slug = request.match_info["slug"]
    ip   = request.headers.get("X-Forwarded-For", request.remote)
    bot  = request.app["bot"]

    meta = ip
    try:
        data = await request.json()
        if isinstance(data, dict) and data.get("meta"):
            meta = str(data["meta"])[:255]
    except Exception:
        pass

    async with async_session() as session:
        link = await session.scalar(select(Link).where(Link.slug == slug))

        if not link or not link.is_active:
            raise web.HTTPNotFound(text="Link not found")

        # Записываем лид
        stat = Stat(link_id=link.id, event="lead", meta=meta)
        session.add(stat)
        await session.commit()

        # Уведомляем воркера (после commit чтобы счётчик был актуальным)
        from bot.utils.notifier import notify_worker_lead
        async with async_session() as notify_session:
            await notify_worker_lead(bot, notify_session, slug, meta)

    logger.info(f"Lead recorded: slug={slug} meta={meta}")
    return web.json_response({"status": "ok"})


# ──────────────────────────────────────────────
# GET /health
# ──────────────────────────────────────────────
async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})
