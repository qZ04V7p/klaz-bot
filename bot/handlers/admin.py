from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Domain, Landing, Link, Stat
from bot.keyboards.inline import (
    admin_main_menu,
    back_to_menu,
    workers_keyboard,
    worker_manage_keyboard,
    domains_keyboard,
    domain_detail_keyboard,
    landings_keyboard,
    confirm_keyboard,
)
from config import settings

router = Router()


# ──────────────────────────────────────────────
# Фильтр: только админы
# ──────────────────────────────────────────────
class IsAdmin(Filter):
    async def __call__(self, event, db_user: User) -> bool:
        return db_user.role == "admin"


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ──────────────────────────────────────────────
# FSM состояния
# ──────────────────────────────────────────────
class AdminStates(StatesGroup):
    waiting_landing_name = State()
    waiting_landing_url  = State()
    waiting_domain       = State()


# ──────────────────────────────────────────────
# Главная панель админа
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:menu")
async def admin_panel(call: CallbackQuery, session: AsyncSession) -> None:
    # Быстрая сводка
    total_workers = await session.scalar(
        select(func.count(User.id)).where(User.role == "worker")
    ) or 0
    total_domains = await session.scalar(select(func.count(Domain.id))) or 0
    total_links   = await session.scalar(select(func.count(Link.id))) or 0

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    clicks_24h = await session.scalar(
        select(func.count(Stat.id)).where(
            and_(Stat.event == "click", Stat.created_at >= since_24h)
        )
    ) or 0
    leads_24h = await session.scalar(
        select(func.count(Stat.id)).where(
            and_(Stat.event == "lead", Stat.created_at >= since_24h)
        )
    ) or 0

    await call.message.edit_text(
        f"<b>⚙️ KLEIN · Админ-панель</b>\n\n"
        f"👥 Воркеры: <b>{total_workers}</b>\n"
        f"🌐 Домены: <b>{total_domains}</b>\n"
        f"🔗 Ссылки: <b>{total_links}</b>\n\n"
        f"📊 <b>Сводка · 24 часа</b>\n"
        f"├ 👁 Переходы: <b>{clicks_24h}</b>\n"
        f"└ 💰 Лиды: <b>{leads_24h}</b>",
        reply_markup=admin_main_menu(),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Список воркеров
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:workers")
async def admin_workers(call: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(User).where(User.role == "worker").order_by(User.created_at.desc())
    )
    workers = result.scalars().all()

    await call.message.edit_text(
        f"👥 <b>Воркеры</b> ({len(workers)})\n\n"
        f"🟢 — активен  ·  🔴 — заблокирован",
        reply_markup=workers_keyboard(workers),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Профиль воркера (для админа)
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin:worker_info:"))
async def admin_worker_info(call: CallbackQuery, session: AsyncSession) -> None:
    worker_id = int(call.data.split(":")[2])
    worker = await session.get(User, worker_id)
    if not worker:
        await call.answer("Воркер не найден", show_alert=True)
        return

    name   = worker.username and f"@{worker.username}" or worker.full_name or "—"
    status = "🟢 Активен" if worker.is_active else "🔴 Заблокирован"
    last   = worker.last_seen.strftime("%d.%m.%Y %H:%M") if worker.last_seen else "ещё не было"

    # Статистика
    clicks = await session.scalar(
        select(func.count(Stat.id))
        .join(Link, Link.id == Stat.link_id)
        .where(and_(Link.worker_id == worker_id, Stat.event == "click"))
    ) or 0
    leads = await session.scalar(
        select(func.count(Stat.id))
        .join(Link, Link.id == Stat.link_id)
        .where(and_(Link.worker_id == worker_id, Stat.event == "lead"))
    ) or 0

    links_count = await session.scalar(
        select(func.count(Link.id)).where(Link.worker_id == worker_id)
    ) or 0

    await call.message.edit_text(
        f"👤 <b>Воркер: {name}</b>\n\n"
        f"ID: <code>{worker.tg_id}</code>\n"
        f"Статус: {status}\n"
        f"Последний заход: {last}\n"
        f"Ссылок: <b>{links_count}</b>\n\n"
        f"📊 Всего:\n"
        f"├ 👁 Переходы: <b>{clicks}</b>\n"
        f"└ 💰 Лиды: <b>{leads}</b>",
        reply_markup=worker_manage_keyboard(worker_id, worker.is_active),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Блок/разблок воркера
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin:worker_toggle:"))
async def admin_worker_toggle(call: CallbackQuery, session: AsyncSession) -> None:
    worker_id = int(call.data.split(":")[2])
    worker = await session.get(User, worker_id)
    if not worker:
        await call.answer("Воркер не найден", show_alert=True)
        return

    worker.is_active = not worker.is_active
    action = "🟢 Разблокирован" if worker.is_active else "🔴 Заблокирован"
    name = worker.username and f"@{worker.username}" or str(worker.tg_id)

    await call.message.edit_text(
        f"✅ Воркер {name} — {action}",
        reply_markup=worker_manage_keyboard(worker_id, worker.is_active),
    )
    await call.answer()


# ──────────────────────────────────────────────
# Назначить лендинг воркеру — показать список
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin:assign_landing:"))
async def admin_assign_landing(call: CallbackQuery, session: AsyncSession) -> None:
    worker_id = int(call.data.split(":")[2])
    result = await session.execute(
        select(Landing).where(Landing.is_active == True)
    )
    landings = result.scalars().all()

    if not landings:
        await call.message.edit_text(
            "⚠️ Нет доступных лендингов. Сначала добавьте лендинг.",
            reply_markup=back_to_menu("admin"),
        )
    else:
        await call.message.edit_text(
            "🖥 Выберите лендинг для привязки:",
            reply_markup=landings_keyboard(landings, worker_id=worker_id),
        )
    await call.answer()


# ──────────────────────────────────────────────
# Назначить лендинг воркеру — применить
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin:set_landing:"))
async def admin_set_landing(call: CallbackQuery, session: AsyncSession) -> None:
    _, _, worker_id_str, landing_id_str = call.data.split(":")
    worker_id  = int(worker_id_str)
    landing_id = int(landing_id_str)

    # Деактивируем старые лендинги воркера
    old = await session.execute(
        select(Landing).where(Landing.worker_id == worker_id)
    )
    for l in old.scalars().all():
        l.worker_id = None

    # Привязываем новый
    landing = await session.get(Landing, landing_id)
    if landing:
        landing.worker_id = worker_id
        worker = await session.get(User, worker_id)
        name = worker.username and f"@{worker.username}" or str(worker.tg_id) if worker else str(worker_id)
        await call.message.edit_text(
            f"✅ Лендинг <b>{landing.name}</b> привязан к {name}",
            reply_markup=back_to_menu("admin"),
            parse_mode="HTML",
        )
    else:
        await call.answer("Лендинг не найден", show_alert=True)
    await call.answer()


# ──────────────────────────────────────────────
# Домены (все)
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:domains")
async def admin_domains(call: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(Domain).order_by(Domain.created_at.desc())
    )
    domains = result.scalars().all()

    await call.message.edit_text(
        f"🌐 <b>Все домены</b> ({len(domains)})\n\n"
        f"IP сервера: <code>{settings.SERVER_IP}</code>",
        reply_markup=domains_keyboard(domains, role="admin"),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Добавить домен (от имени админа)
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:add_domain")
async def admin_ask_domain(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(
        f"🌐 <b>Добавление домена</b>\n\n"
        f"Отправьте домен (без https://):\n<code>example.com</code>",
        parse_mode="HTML",
        reply_markup=back_to_menu("admin"),
    )
    await state.set_state(AdminStates.waiting_domain)
    await call.answer()


@router.message(AdminStates.waiting_domain)
async def admin_save_domain(message: Message, state: FSMContext, db_user: User, session: AsyncSession) -> None:
    domain_name = message.text.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")

    existing = await session.scalar(select(Domain).where(Domain.domain == domain_name))
    if existing:
        await message.answer("⚠️ Домен уже существует.", reply_markup=back_to_menu("admin"))
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
        f"✅ Домен <code>{domain_name}</code> добавлен.\n"
        f"Не забудьте прописать A-запись на <code>{settings.SERVER_IP}</code>.",
        parse_mode="HTML",
        reply_markup=admin_main_menu(),
    )
    await state.clear()


# ──────────────────────────────────────────────
# Лендинги
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:landings")
async def admin_landings(call: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(Landing).order_by(Landing.created_at.desc())
    )
    landings = result.scalars().all()

    await call.message.edit_text(
        f"🖥 <b>Лендинги</b> ({len(landings)})",
        reply_markup=landings_keyboard(landings),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Добавить лендинг — название
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:add_landing")
async def admin_ask_landing_name(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(
        "🖥 <b>Добавление лендинга</b>\n\nВведите название лендинга:",
        parse_mode="HTML",
        reply_markup=back_to_menu("admin"),
    )
    await state.set_state(AdminStates.waiting_landing_name)
    await call.answer()


@router.message(AdminStates.waiting_landing_name)
async def admin_landing_name(message: Message, state: FSMContext) -> None:
    await state.update_data(landing_name=message.text.strip())
    await message.answer(
        "🔗 Введите URL лендинга (или <code>-</code> чтобы добавить позже):",
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_landing_url)


@router.message(AdminStates.waiting_landing_url)
async def admin_landing_url(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    name = data.get("landing_name", "Без названия")
    url  = message.text.strip()
    if url == "-":
        url = None

    landing = Landing(name=name, url=url, is_active=True)
    session.add(landing)
    await session.flush()

    await message.answer(
        f"✅ Лендинг <b>{name}</b> добавлен.\n"
        f"URL: {url or '—'}",
        parse_mode="HTML",
        reply_markup=admin_main_menu(),
    )
    await state.clear()


# ──────────────────────────────────────────────
# Глобальная статистика
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:stats")
async def admin_stats(call: CallbackQuery, session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    day_ago  = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    async def count(since, event):
        return await session.scalar(
            select(func.count(Stat.id)).where(
                and_(Stat.event == event, Stat.created_at >= since)
            )
        ) or 0

    c24 = await count(day_ago,  "click")
    l24 = await count(day_ago,  "lead")
    c7d = await count(week_ago, "click")
    l7d = await count(week_ago, "lead")

    c_all = await session.scalar(
        select(func.count(Stat.id)).where(Stat.event == "click")
    ) or 0
    l_all = await session.scalar(
        select(func.count(Stat.id)).where(Stat.event == "lead")
    ) or 0

    workers_count = await session.scalar(
        select(func.count(User.id)).where(User.role == "worker")
    ) or 0
    links_count = await session.scalar(select(func.count(Link.id))) or 0

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📤 Экспорт отчёта", callback_data="admin:export"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:menu"))

    await call.message.edit_text(
        f"📊 <b>Глобальная статистика</b>\n\n"
        f"👥 Воркеры: <b>{workers_count}</b>\n"
        f"🔗 Ссылок: <b>{links_count}</b>\n\n"
        f"<b>24 часа:</b>\n"
        f"├ 👁 Переходы: <b>{c24}</b>\n"
        f"└ 💰 Лиды: <b>{l24}</b>\n\n"
        f"<b>7 дней:</b>\n"
        f"├ 👁 Переходы: <b>{c7d}</b>\n"
        f"└ 💰 Лиды: <b>{l7d}</b>\n\n"
        f"<b>Всего:</b>\n"
        f"├ 👁 Переходы: <b>{c_all}</b>\n"
        f"└ 💰 Лиды: <b>{l_all}</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    await call.answer()


# ──────────────────────────────────────────────
# Экспорт глобального отчёта (для админа)
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:export")
async def admin_export(call: CallbackQuery, session: AsyncSession) -> None:
    now      = datetime.now(timezone.utc)
    day_ago  = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    async def cnt(event, since=None):
        q = select(func.count(Stat.id)).where(Stat.event == event)
        if since:
            q = q.where(Stat.created_at >= since)
        return await session.scalar(q) or 0

    c24  = await cnt("click", day_ago)
    l24  = await cnt("lead",  day_ago)
    c7d  = await cnt("click", week_ago)
    l7d  = await cnt("lead",  week_ago)
    c_all = await cnt("click")
    l_all = await cnt("lead")

    # Воркеры
    workers_res = await session.execute(
        select(User).where(User.role == "worker").order_by(User.created_at.desc())
    )
    workers = workers_res.scalars().all()

    # Домены
    domains_res = await session.execute(select(Domain).order_by(Domain.created_at.desc()))
    domains = domains_res.scalars().all()
    verified_cnt = sum(1 for d in domains if d.is_verified)

    # Лендинги
    landings_res = await session.execute(select(Landing))
    landings = landings_res.scalars().all()

    ts = now.strftime("%d.%m.%Y %H:%M")

    lines = [
        "📋 <b>Глобальный отчёт KLEIN</b>",
        f"🕐 {ts} UTC",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "📊 <b>ОБЩАЯ СТАТИСТИКА</b>",
        f"  24ч   👁 {c24}  💰 {l24}",
        f"  7д    👁 {c7d}  💰 {l7d}",
        f"  Всего 👁 {c_all}  💰 {l_all}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        f"👥 <b>ВОРКЕРЫ</b> ({len(workers)})",
    ]

    for w in workers:
        name = w.username and f"@{w.username}" or w.full_name or str(w.tg_id)
        status = "🟢" if w.is_active else "🔴"

        wc = await session.scalar(
            select(func.count(Stat.id))
            .join(Link, Link.id == Stat.link_id)
            .where(and_(Link.worker_id == w.id, Stat.event == "click"))
        ) or 0
        wl = await session.scalar(
            select(func.count(Stat.id))
            .join(Link, Link.id == Stat.link_id)
            .where(and_(Link.worker_id == w.id, Stat.event == "lead"))
        ) or 0
        wlinks = await session.scalar(
            select(func.count(Link.id)).where(Link.worker_id == w.id)
        ) or 0

        lines.append(f"  {status} {name}  🔗{wlinks} 👁{wc} 💰{wl}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━",
        f"🌐 <b>ДОМЕНЫ</b> ({len(domains)})  ✅{verified_cnt} ⏳{len(domains)-verified_cnt}",
    ]
    for d in domains:
        v = "✅" if d.is_verified else "⏳"
        owner = f"(id={d.worker_id})" if d.worker_id else "(без воркера)"
        lines.append(f"  {v} <code>{d.domain}</code> {owner}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━",
        f"🖥 <b>ЛЕНДИНГИ</b> ({len(landings)})",
    ]
    for l in landings:
        lines.append(f"  • {l.name}  {l.url or '—'}")

    report = "\n".join(lines)
    await call.message.answer(report, parse_mode="HTML", reply_markup=back_to_menu("admin"))
    await call.answer("✅ Отчёт сформирован")


# ──────────────────────────────────────────────
# Настройки
# ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:settings")
async def admin_settings(call: CallbackQuery, db_user: User) -> None:
    name = db_user.username and f"@{db_user.username}" or db_user.full_name or "—"
    await call.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"Имя: {name}\n"
        f"ID: <code>{db_user.tg_id}</code>\n"
        f"Роль: Администратор\n"
        f"IP сервера: <code>{settings.SERVER_IP}</code>",
        reply_markup=back_to_menu("admin"),
        parse_mode="HTML",
    )
    await call.answer()
