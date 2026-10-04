from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from db.models import User
from bot.keyboards.inline import worker_main_menu, admin_main_menu

router = Router()


def _panel_text(user: User) -> str:
    role_map = {"worker": "Воркер", "admin": "Админ"}
    last = (
        user.last_seen.strftime("%d.%m.%Y %H:%M")
        if user.last_seen else "ещё не было"
    )
    return (
        f"<b>⚙️ KLEIN · Панель</b>\n\n"
        f"👤 <b>Профиль</b>\n"
        f"├ Роль · {role_map.get(user.role, user.role)}\n"
        f"├ Режим · Ручной\n"
        f"└ Последний заход · {last}\n\n"
        f"📊 <b>Сводка · 24 часа</b>\n"
        f"├ 👁 Переходы · <code>0</code>\n"
        f"└ 💰 Лиды · <code>0</code>"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User) -> None:
    """Панель для воркеров и админов."""
    if db_user.role not in ("worker", "admin"):
        return  # клиенты обрабатываются в client.py
    text = _panel_text(db_user)
    kb = admin_main_menu() if db_user.role == "admin" else worker_main_menu()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("menu"))
async def cmd_menu(message: Message, db_user: User) -> None:
    if db_user.role not in ("worker", "admin"):
        return
    text = _panel_text(db_user)
    kb = admin_main_menu() if db_user.role == "admin" else worker_main_menu()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(lambda c: c.data in ("worker:menu", "admin:menu"))
async def cb_menu(call: CallbackQuery, db_user: User) -> None:
    text = _panel_text(db_user)
    kb = admin_main_menu() if db_user.role == "admin" else worker_main_menu()
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()
