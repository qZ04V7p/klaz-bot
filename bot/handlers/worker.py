import socket
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Domain, Link, Stat, Landing
from bot.keyboards.inline import (
    worker_main_menu,
    links_keyboard,
    link_detail_keyboard,
    domains_keyboard,
    domain_detail_keyboard,
    confirm_keyboard,
    back_to_menu,
)
from bot.utils.link_generator import create_unique_slug, build_ref_url
from config import settings

router = Router()


# ──────────────────────────────────────────────
# FSM состояния
# ──────────────────────────────────────────────
class WorkerStates(StatesGroup):
    waiting_link_label = State()
    waiting_domain = State()


# ──────────────────────────────────────────────
# Панель воркера
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:menu")
async def worker_panel(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    text = await _build_panel(db_user, session)
    await call.message.edit_text(text, reply_markup=worker_main_menu(), parse_mode="HTML")
    await call.answer()


async def _build_panel(user: User, session: AsyncSession) -> str:
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    # Считаем клики за 24ч
    clicks = await session.scalar(
        select(func.count(Stat.id))
        .join(Link, Link.id == Stat.link_id)
        .where(and_(Link.worker_id == user.id, Stat.event == "click", Stat.created_at >= since))
    ) or 0

    # Считаем лиды за 24ч
    leads = await session.scalar(
        select(func.count(Stat.id))
        .join(Link, Link.id == Stat.link_id)
        .where(and_(Link.worker_id == user.id, Stat.event == "lead", Stat.created_at >= since))
    ) or 0

    last = (
        user.last_seen.strftime("%d.%m.%Y %H:%M")
        if user.last_seen else "ещё не было"
    )

    # Активный лендинг
    landing_name = "не привязан"
    active_landing = await session.scalar(
        select(Landing).where(and_(Landing.worker_id == user.id, Landing.is_active == True))
    )
    if active_landing:
        landing_name = active_landing.url or active_landing.name

    return (
        f"<b>⚙️ KLEIN · Панель</b>\n\n"
        f"👤 <b>Профиль</b>\n"
        f"├ Роль · Воркер\n"
        f"├ Режим · Ручной\n"
        f"├ Лендинг · <code>{landing_name}</code>\n"
        f"└ Последний заход · {last}\n\n"
        f"📊 <b>Сводка · 24 часа</b>\n"
        f"├ 👁 Переходы · <b>{clicks}</b>\n"
        f"└ 💰 Лиды · <b>{leads}</b>"
    )


# ──────────────────────────────────────────────
# Создать ссылку — шаг 1: спросить название
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:create_link")
async def ask_link_label(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(
        "🔗 <b>Создание ссылки</b>\n\n"
        "Введите название (метку) для ссылки, или отправьте <code>-</code> чтобы пропустить:",
        parse_mode="HTML",
        reply_markup=back_to_menu("worker"),
    )
    await state.set_state(WorkerStates.waiting_link_label)
    await call.answer()


# ──────────────────────────────────────────────
# Создать ссылку — шаг 2: сохранить
# ──────────────────────────────────────────────
@router.message(WorkerStates.waiting_link_label)
async def save_link(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    label = message.text.strip()
    if label == "-":
        label = None

    slug = await create_unique_slug(session)

    # Ищем активный лендинг и домен воркера
    landing = await session.scalar(
        select(Landing).where(and_(Landing.worker_id == db_user.id, Landing.is_active == True))
    )
    domain_obj = await session.scalar(
        select(Domain).where(and_(Domain.worker_id == db_user.id, Domain.is_verified == True))
    )

    link = Link(
        slug=slug,
        label=label,
        worker_id=db_user.id,
        landing_id=landing.id if landing else None,
    )
    session.add(link)
    await session.flush()

    domain_name = domain_obj.domain if domain_obj else None
    ref_url = build_ref_url(slug, domain_name)

    await message.answer(
        f"✅ <b>Ссылка создана!</b>\n\n"
        f"🔗 <code>{ref_url}</code>\n\n"
        f"📎 Метка: {label or '—'}\n"
        f"🆔 Slug: <code>{slug}</code>",
        parse_mode="HTML",
        reply_markup=worker_main_menu(),
    )
    await state.clear()


# ──────────────────────────────────────────────
# Мои ссылки
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:my_links")
async def my_links(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    result = await session.execute(
        select(Link).where(Link.worker_id == db_user.id).order_by(Link.created_at.desc())
    )
    links = result.scalars().all()

    if not links:
        await call.message.edit_text(
            "📭 У вас пока нет ссылок.\n\nСоздайте первую!",
            reply_markup=worker_main_menu(),
        )
    else:
        await call.message.edit_text(
            f"📎 <b>Мои ссылки</b> ({len(links)})",
            reply_markup=links_keyboard(links),
            parse_mode="HTML",
        )
    await call.answer()


# ──────────────────────────────────────────────
# Информация о ссылке
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("link:info:"))
async def link_info(call: CallbackQuery, session: AsyncSession) -> None:
    link_id = int(call.data.split(":")[2])
    link = await session.get(Link, link_id)
    if not link:
        await call.answer("Ссылка не найдена", show_alert=True)
        return

    # Статистика по ссылке
    clicks = await session.scalar(
        select(func.count(Stat.id)).where(and_(Stat.link_id == link_id, Stat.event == "click"))
    ) or 0
    leads = await session.scalar(
        select(func.count(Stat.id)).where(and_(Stat.link_id == link_id, Stat.event == "lead"))
    ) or 0

    domain_obj = None
    if link.landing_id:
        landing = await session.get(Landing, link.landing_id)
        if landing and landing.domain_id:
            domain_obj = await session.get(Domain, landing.domain_id)

    domain_name = domain_obj.domain if domain_obj else None
    ref_url = build_ref_url(link.slug, domain_name)

    await call.message.edit_text(
        f"🔗 <b>Ссылка</b>\n\n"
        f"Метка: {link.label or '—'}\n"
        f"URL: <code>{ref_url}</code>\n"
        f"Slug: <code>{link.slug}</code>\n\n"
        f"👁 Переходы: <b>{clicks}</b>\n"
        f"💰 Лиды: <b>{leads}</b>\n"
        f"📅 Создана: {link.created_at.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=link_detail_keyboard(link_id),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Удалить ссылку
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("link:delete:"))
async def link_delete_confirm(call: CallbackQuery) -> None:
    link_id = call.data.split(":")[2]
    await call.message.edit_text(
        "❓ Вы уверены, что хотите удалить эту ссылку?\nСтатистика будет потеряна.",
        reply_markup=confirm_keyboard(
            yes_cb=f"link:delete_yes:{link_id}",
            no_cb=f"link:info:{link_id}",
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("link:delete_yes:"))
async def link_delete_do(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    link_id = int(call.data.split(":")[2])
    link = await session.get(Link, link_id)
    if link and link.worker_id == db_user.id:
        await session.delete(link)
        await call.message.edit_text(
            "🗑 Ссылка удалена.",
            reply_markup=worker_main_menu(),
        )
    else:
        await call.answer("Нет доступа", show_alert=True)
    await call.answer()


# ──────────────────────────────────────────────
# Домены воркера
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:domains")
async def worker_domains(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    result = await session.execute(
        select(Domain).where(Domain.worker_id == db_user.id)
    )
    domains = result.scalars().all()

    await call.message.edit_text(
        f"🌐 <b>Мои домены</b> ({len(domains)})\n\n"
        f"✅ — DNS настроен  ·  ⏳ — ожидает проверки\n\n"
        f"IP сервера: <code>{settings.SERVER_IP}</code>",
        reply_markup=domains_keyboard(domains, role="worker"),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Добавить домен — запрос
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:add_domain")
async def ask_domain(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(
        f"🌐 <b>Добавление домена</b>\n\n"
        f"Пропишите A-запись вашего домена на IP:\n"
        f"<code>{settings.SERVER_IP}</code>\n\n"
        f"Затем отправьте домен (без https://):\n"
        f"Пример: <code>mysite.com</code>",
        parse_mode="HTML",
        reply_markup=back_to_menu("worker"),
    )
    await state.set_state(WorkerStates.waiting_domain)
    await call.answer()


# ──────────────────────────────────────────────
# Добавить домен — сохранить
# ──────────────────────────────────────────────
@router.message(WorkerStates.waiting_domain)
async def save_domain(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    domain_name = message.text.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")

    # Проверяем, не занят ли домен
    existing = await session.scalar(select(Domain).where(Domain.domain == domain_name))
    if existing:
        await message.answer(
            "⚠️ Этот домен уже зарегистрирован. Введите другой:",
            reply_markup=back_to_menu("worker"),
        )
        return

    domain = Domain(
        domain=domain_name,
        expected_ip=settings.SERVER_IP,
        is_verified=False,
        worker_id=db_user.id,
    )
    session.add(domain)
    await session.flush()

    await message.answer(
        f"✅ <b>Домен добавлен!</b>\n\n"
        f"🌐 <code>{domain_name}</code>\n"
        f"⏳ Статус: ожидает проверки DNS\n\n"
        f"Убедитесь, что A-запись указывает на:\n"
        f"<code>{settings.SERVER_IP}</code>\n\n"
        f"Затем нажмите «Проверить DNS» в разделе домена.",
        parse_mode="HTML",
        reply_markup=worker_main_menu(),
    )
    await state.clear()


# ──────────────────────────────────────────────
# Информация о домене
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("domain:info:"))
async def domain_info(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    domain_id = int(call.data.split(":")[2])
    domain = await session.get(Domain, domain_id)
    if not domain:
        await call.answer("Домен не найден", show_alert=True)
        return

    # Определяем роль для кнопки назад
    role = db_user.role
    status = "✅ Подтверждён" if domain.is_verified else "⏳ Ожидает проверки"

    await call.message.edit_text(
        f"🌐 <b>Домен</b>: <code>{domain.domain}</code>\n\n"
        f"Статус: {status}\n"
        f"IP: <code>{domain.expected_ip or settings.SERVER_IP}</code>\n"
        f"Добавлен: {domain.created_at.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=domain_detail_keyboard(domain_id, role=role),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Проверить DNS домена
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("domain:verify:"))
async def domain_verify(call: CallbackQuery, session: AsyncSession) -> None:
    domain_id = int(call.data.split(":")[2])
    domain = await session.get(Domain, domain_id)
    if not domain:
        await call.answer("Домен не найден", show_alert=True)
        return

    await call.answer("🔄 Проверяю DNS...", show_alert=False)

    try:
        resolved_ip = socket.gethostbyname(domain.domain)
        if resolved_ip == (domain.expected_ip or settings.SERVER_IP):
            domain.is_verified = True
            status_text = f"✅ DNS подтверждён!\nIP: <code>{resolved_ip}</code>"
        else:
            domain.is_verified = False
            status_text = (
                f"❌ DNS не совпадает!\n"
                f"Ожидается: <code>{domain.expected_ip or settings.SERVER_IP}</code>\n"
                f"Найдено: <code>{resolved_ip}</code>"
            )
    except socket.gaierror:
        domain.is_verified = False
        status_text = f"❌ Домен не резолвится. Проверьте A-запись."

    await call.message.edit_text(
        f"🌐 <b>{domain.domain}</b>\n\n{status_text}",
        reply_markup=domain_detail_keyboard(domain_id),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────
# Удалить домен
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("domain:delete:"))
async def domain_delete_confirm(call: CallbackQuery) -> None:
    domain_id = call.data.split(":")[2]
    await call.message.edit_text(
        "❓ Удалить этот домен?",
        reply_markup=confirm_keyboard(
            yes_cb=f"domain:delete_yes:{domain_id}",
            no_cb=f"domain:info:{domain_id}",
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("domain:delete_yes:"))
async def domain_delete_do(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    domain_id = int(call.data.split(":")[2])
    domain = await session.get(Domain, domain_id)
    if domain and (domain.worker_id == db_user.id or db_user.role == "admin"):
        await session.delete(domain)
        await call.message.edit_text(
            "🗑 Домен удалён.",
            reply_markup=worker_main_menu() if db_user.role == "worker" else None,
        )
    else:
        await call.answer("Нет доступа", show_alert=True)
    await call.answer()


# ──────────────────────────────────────────────
# Статистика воркера
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:stats")
async def worker_stats(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    day_ago  = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    async def count_events(since, event):
        return await session.scalar(
            select(func.count(Stat.id))
            .join(Link, Link.id == Stat.link_id)
            .where(and_(
                Link.worker_id == db_user.id,
                Stat.event == event,
                Stat.created_at >= since,
            ))
        ) or 0

    clicks_24h = await count_events(day_ago,  "click")
    leads_24h  = await count_events(day_ago,  "lead")
    clicks_7d  = await count_events(week_ago, "click")
    leads_7d   = await count_events(week_ago, "lead")

    clicks_all = await session.scalar(
        select(func.count(Stat.id))
        .join(Link, Link.id == Stat.link_id)
        .where(and_(Link.worker_id == db_user.id, Stat.event == "click"))
    ) or 0
    leads_all = await session.scalar(
        select(func.count(Stat.id))
        .join(Link, Link.id == Stat.link_id)
        .where(and_(Link.worker_id == db_user.id, Stat.event == "lead"))
    ) or 0

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📤 Экспорт отчёта", callback_data="worker:export"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="worker:menu"))

    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"<b>24 часа:</b>\n"
        f"├ 👁 Переходы: <b>{clicks_24h}</b>\n"
        f"└ 💰 Лиды: <b>{leads_24h}</b>\n\n"
        f"<b>7 дней:</b>\n"
        f"├ 👁 Переходы: <b>{clicks_7d}</b>\n"
        f"└ 💰 Лиды: <b>{leads_7d}</b>\n\n"
        f"<b>Всего:</b>\n"
        f"├ 👁 Переходы: <b>{clicks_all}</b>\n"
        f"└ 💰 Лиды: <b>{leads_all}</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Экспорт статистики воркера
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:export")
async def worker_export(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    day_ago  = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    # Все ссылки воркера
    result = await session.execute(
        select(Link).where(Link.worker_id == db_user.id).order_by(Link.created_at.desc())
    )
    links = result.scalars().all()

    # Все домены воркера
    dom_result = await session.execute(
        select(Domain).where(Domain.worker_id == db_user.id)
    )
    domains = dom_result.scalars().all()

    # Глобальные счётчики
    async def cnt(worker_id, event, since=None):
        q = (
            select(func.count(Stat.id))
            .join(Link, Link.id == Stat.link_id)
            .where(and_(Link.worker_id == worker_id, Stat.event == event))
        )
        if since:
            q = q.where(Stat.created_at >= since)
        return await session.scalar(q) or 0

    c24  = await cnt(db_user.id, "click", day_ago)
    l24  = await cnt(db_user.id, "lead",  day_ago)
    c7d  = await cnt(db_user.id, "click", week_ago)
    l7d  = await cnt(db_user.id, "lead",  week_ago)
    c_all = await cnt(db_user.id, "click")
    l_all = await cnt(db_user.id, "lead")

    name = db_user.username and f"@{db_user.username}" or db_user.full_name or str(db_user.tg_id)
    ts   = now.strftime("%d.%m.%Y %H:%M")

    # ── Формируем текст отчёта ──
    lines = [
        f"📋 <b>Отчёт воркера</b>",
        f"👤 {name}  |  🕐 {ts} UTC",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "📊 <b>СТАТИСТИКА</b>",
        f"  24ч   👁 {c24}  💰 {l24}",
        f"  7д    👁 {c7d}  💰 {l7d}",
        f"  Всего 👁 {c_all}  💰 {l_all}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        f"🔗 <b>ССЫЛКИ</b> ({len(links)})",
    ]

    for lnk in links:
        lc = await session.scalar(
            select(func.count(Stat.id)).where(
                and_(Stat.link_id == lnk.id, Stat.event == "click")
            )
        ) or 0
        ll = await session.scalar(
            select(func.count(Stat.id)).where(
                and_(Stat.link_id == lnk.id, Stat.event == "lead")
            )
        ) or 0
        label = lnk.label or lnk.slug
        lines.append(f"  • <code>{lnk.slug}</code> [{label}]  👁{lc} 💰{ll}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━",
        f"🌐 <b>ДОМЕНЫ</b> ({len(domains)})",
    ]
    for d in domains:
        verified = "✅" if d.is_verified else "⏳"
        lines.append(f"  {verified} <code>{d.domain}</code>")

    # Активный лендинг
    landing = await session.scalar(
        select(Landing).where(and_(Landing.worker_id == db_user.id, Landing.is_active == True))
    )
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━",
        f"🖥 <b>ЛЕНДИНГ</b>: {landing.url or landing.name if landing else '—'}",
    ]

    report = "\n".join(lines)

    # Отправляем отдельным сообщением (не редактируем — отчёт длинный)
    await call.message.answer(report, parse_mode="HTML", reply_markup=back_to_menu("worker"))
    await call.answer("✅ Отчёт сформирован")


# ──────────────────────────────────────────────
# Настройки воркера
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:settings")
async def worker_settings(call: CallbackQuery, db_user: User) -> None:
    name = db_user.username and f"@{db_user.username}" or db_user.full_name or "—"
    await call.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"Имя: {name}\n"
        f"ID: <code>{db_user.tg_id}</code>\n"
        f"Роль: Воркер\n"
        f"Режим: Ручной",
        reply_markup=back_to_menu("worker"),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Справка
# ──────────────────────────────────────────────
@router.callback_query(F.data == "worker:help")
async def worker_help(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "ℹ️ <b>Справка</b>\n\n"
        "🔗 <b>Создать ссылку</b> — генерация реф-ссылки\n"
        "📎 <b>Мои ссылки</b> — список ссылок и статистика\n"
        "🌐 <b>Домены</b> — добавить личный домен (нужна A-запись на IP сервера)\n"
        "📊 <b>Статистика</b> — переходы и лиды\n\n"
        "По вопросам обращайтесь к администратору.",
        reply_markup=back_to_menu("worker"),
        parse_mode="HTML",
    )
    await call.answer()
