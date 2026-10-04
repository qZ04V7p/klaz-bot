from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import CommandStart, Filter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Application

router = Router()


class IsClient(Filter):
    async def __call__(self, message: Message, db_user: User) -> bool:
        return db_user.role not in ("worker", "admin")


def client_start_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Подать заявку", callback_data="client:apply"))
    return builder.as_markup()


def application_kb(app_id: int, tg_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"app:accept:{app_id}:{tg_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"app:reject:{app_id}:{tg_id}"),
    )
    return builder.as_markup()


@router.message(CommandStart(), IsClient())
async def client_start(message: Message, db_user: User) -> None:
    """Только для клиентов."""
    name = message.from_user.full_name or "друг"
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        f"Нажми кнопку ниже чтобы подать заявку.",
        reply_markup=client_start_kb(),
    )


@router.callback_query(F.data == "client:apply")
async def client_apply(call: CallbackQuery, db_user: User, session: AsyncSession) -> None:
    # Сохраняем заявку
    app = Application(
        tg_id=db_user.tg_id,
        username=db_user.username,
        full_name=db_user.full_name,
    )
    session.add(app)
    await session.flush()

    # Подтверждение пользователю
    await call.message.edit_text(
        "✅ Ваша заявка принята!\n\n"
        "Мы свяжемся с вами в ближайшее время.",
    )
    await call.answer()

    # Уведомляем всех админов с кнопками
    admins = await session.execute(
        select(User).where(User.role == "admin", User.is_active == True)
    )
    admins = admins.scalars().all()

    name = db_user.full_name or "—"
    username = f"@{db_user.username}" if db_user.username else "нет"
    ts = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")

    text = (
        f"📋 <b>Новая заявка!</b>\n\n"
        f"👤 Имя: {name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 TG ID: <code>{db_user.tg_id}</code>\n"
        f"🕐 Время: {ts} UTC"
    )

    bot = call.bot
    for admin in admins:
        try:
            await bot.send_message(
                admin.tg_id,
                text,
                parse_mode="HTML",
                reply_markup=application_kb(app.id, db_user.tg_id),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("app:accept:"))
async def app_accept(call: CallbackQuery, session: AsyncSession) -> None:
    parts = call.data.split(":")
    app_id = int(parts[2])
    user_tg_id = int(parts[3])

    # Меняем роль пользователя на воркера
    user = await session.scalar(select(User).where(User.tg_id == user_tg_id))
    if user:
        user.role = "worker"

    # Обновляем текст сообщения у админа
    await call.message.edit_text(
        call.message.html_text + "\n\n✅ <b>Принято — стал воркером</b>",
        parse_mode="HTML",
    )
    await call.answer("✅ Заявка принята, пользователь стал воркером")

    # Уведомляем пользователя и показываем панель воркера
    from bot.keyboards.inline import worker_main_menu
    try:
        await call.bot.send_message(
            user_tg_id,
            "✅ Ваша заявка <b>одобрена!</b>\n\n"
            "Добро пожаловать в команду! Теперь у вас есть доступ к панели воркера.",
            parse_mode="HTML",
        )
        await call.bot.send_message(
            user_tg_id,
            "<b>⚙️ KLEIN · Панель</b>\n\n"
            "👤 <b>Профиль</b>\n"
            "├ Роль · Воркер\n"
            "├ Режим · Ручной\n"
            "└ Добро пожаловать!\n\n"
            "📊 <b>Сводка · 24 часа</b>\n"
            "├ 👁 Переходы · <b>0</b>\n"
            "└ 💰 Лиды · <b>0</b>",
            parse_mode="HTML",
            reply_markup=worker_main_menu(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("app:reject:"))
async def app_reject(call: CallbackQuery, session: AsyncSession) -> None:
    parts = call.data.split(":")
    app_id = int(parts[2])
    user_tg_id = int(parts[3])

    await call.message.edit_text(
        call.message.html_text + "\n\n❌ <b>Отклонено</b>",
        parse_mode="HTML",
    )
    await call.answer("❌ Заявка отклонена")

    try:
        await call.bot.send_message(
            user_tg_id,
            "❌ Ваша заявка <b>отклонена.</b>\n\nЕсли есть вопросы — свяжитесь с поддержкой.",
            parse_mode="HTML",
        )
    except Exception:
        pass
