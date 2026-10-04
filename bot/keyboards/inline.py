from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ──────────────────────────────────────────────
# Главное меню воркера
# ──────────────────────────────────────────────
def worker_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔗 Создать ссылку", callback_data="worker:create_link")
    )
    builder.row(
        InlineKeyboardButton(text="📎 Мои ссылки",   callback_data="worker:my_links"),
        InlineKeyboardButton(text="🌐 Домены",        callback_data="worker:domains"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика",    callback_data="worker:stats"),
        InlineKeyboardButton(text="⚙️ Настройки",     callback_data="worker:settings"),
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Справка",       callback_data="worker:help"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Главное меню админа
# ──────────────────────────────────────────────
def admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Воркеры",       callback_data="admin:workers"),
        InlineKeyboardButton(text="🌐 Домены",        callback_data="admin:domains"),
    )
    builder.row(
        InlineKeyboardButton(text="🖥 Лендинги",      callback_data="admin:landings"),
        InlineKeyboardButton(text="📊 Статистика",    callback_data="admin:stats"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки",     callback_data="admin:settings"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Кнопка «Назад»
# ──────────────────────────────────────────────
def back_to_menu(role: str = "worker") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data=f"{role}:menu")
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Список ссылок воркера (динамический)
# ──────────────────────────────────────────────
def links_keyboard(links: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for link in links:
        label = link.label or link.slug
        builder.row(
            InlineKeyboardButton(
                text=f"🔗 {label}",
                callback_data=f"link:info:{link.id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Создать ссылку", callback_data="worker:create_link"),
        InlineKeyboardButton(text="◀️ Назад",          callback_data="worker:menu"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Детали ссылки
# ──────────────────────────────────────────────
def link_detail_keyboard(link_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"link:delete:{link_id}"),
        InlineKeyboardButton(text="◀️ Назад",   callback_data="worker:my_links"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Домены воркера (динамический)
# ──────────────────────────────────────────────
def domains_keyboard(domains: list, role: str = "worker") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d in domains:
        verified = "✅" if d.is_verified else "⏳"
        builder.row(
            InlineKeyboardButton(
                text=f"{verified} {d.domain}",
                callback_data=f"domain:info:{d.id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить домен", callback_data=f"{role}:add_domain"),
        InlineKeyboardButton(text="◀️ Назад",          callback_data=f"{role}:menu"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Детали домена
# ──────────────────────────────────────────────
def domain_detail_keyboard(domain_id: int, role: str = "worker") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Проверить DNS",  callback_data=f"domain:verify:{domain_id}"),
        InlineKeyboardButton(text="🗑 Удалить",        callback_data=f"domain:delete:{domain_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"{role}:domains")
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Список воркеров для админа (динамический)
# ──────────────────────────────────────────────
def workers_keyboard(workers: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for w in workers:
        name = w.username and f"@{w.username}" or w.full_name or str(w.tg_id)
        status = "🟢" if w.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {name}",
                callback_data=f"admin:worker_info:{w.id}"
            )
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:menu")
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Управление воркером (для админа)
# ──────────────────────────────────────────────
def worker_manage_keyboard(worker_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔴 Заблокировать" if is_active else "🟢 Разблокировать"
    builder.row(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data=f"admin:worker_toggle:{worker_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🖥 Назначить лендинг",
            callback_data=f"admin:assign_landing:{worker_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:workers")
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Список лендингов (для назначения)
# ──────────────────────────────────────────────
def landings_keyboard(landings: list, worker_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for l in landings:
        cb = f"admin:set_landing:{worker_id}:{l.id}" if worker_id else f"landing:info:{l.id}"
        builder.row(
            InlineKeyboardButton(text=f"🖥 {l.name}", callback_data=cb)
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить лендинг", callback_data="admin:add_landing"),
        InlineKeyboardButton(text="◀️ Назад",            callback_data="admin:menu"),
    )
    return builder.as_markup()


# ──────────────────────────────────────────────
# Подтверждение (да / нет)
# ──────────────────────────────────────────────
def confirm_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да",   callback_data=yes_cb),
        InlineKeyboardButton(text="❌ Нет",  callback_data=no_cb),
    )
    return builder.as_markup()
