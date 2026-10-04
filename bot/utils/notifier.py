from datetime import datetime, timezone

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Link, User, Stat


async def notify_worker_lead(bot: Bot, session: AsyncSession, slug: str, meta: str | None = None) -> None:
    """
    Находит воркера по slug ссылки и отправляет ему уведомление о новом лиде.
    """
    link = await session.scalar(select(Link).where(Link.slug == slug))
    if not link or not link.worker_id:
        return

    worker = await session.get(User, link.worker_id)
    if not worker or not worker.is_active:
        return

    # Считаем всего лидов по этой ссылке
    from sqlalchemy import func, and_
    total_leads = await session.scalar(
        select(func.count(Stat.id)).where(
            and_(Stat.link_id == link.id, Stat.event == "lead")
        )
    ) or 0

    label = link.label or link.slug
    now = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")

    text = (
        f"🔔 <b>Новый лид!</b>\n\n"
        f"🔗 Ссылка: <code>{label}</code>\n"
        f"🆔 Slug: <code>{slug}</code>\n"
        f"💰 Всего лидов по ссылке: <b>{total_leads}</b>\n"
        f"🕐 Время: {now} UTC"
    )

    if meta:
        text += f"\n📋 Мета: <code>{meta}</code>"

    try:
        await bot.send_message(worker.tg_id, text, parse_mode="HTML")
    except Exception:
        pass  # воркер мог заблокировать бота


async def notify_worker_click(bot: Bot, session: AsyncSession, slug: str) -> None:
    """
    Опциональное уведомление о клике (по умолчанию не шлём — слишком шумно).
    Можно включить позже через настройки воркера.
    """
    pass
