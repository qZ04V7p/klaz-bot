import asyncio
import logging

import aiohttp
from aiohttp import web
from aiohttp_socks import ProxyConnector
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import settings
from db.database import init_db
from bot.middlewares.auth import AuthMiddleware
from bot.handlers import common_router, worker_router, admin_router, client_router
from tracker import create_tracker_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TRACKER_HOST = "0.0.0.0"
TRACKER_PORT = 8080


class ProxiedSession(AiohttpSession):
    """AiohttpSession с постоянным SOCKS5 коннектором."""

    def __init__(self, proxy_url: str):
        super().__init__()
        self._proxy_url = proxy_url
        self._connector = ProxyConnector.from_url(proxy_url, rdns=True)
        self._client = aiohttp.ClientSession(connector=self._connector)

    async def create_session(self) -> aiohttp.ClientSession:
        return self._client

    async def close(self) -> None:
        if not self._client.closed:
            await self._client.close()


async def run_bot(bot: Bot, dp: Dispatcher) -> None:
    logger.info("Starting Telegram bot...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


async def run_tracker(bot: Bot) -> None:
    app = create_tracker_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, TRACKER_HOST, TRACKER_PORT)
    await site.start()
    logger.info(f"Tracker started on http://{TRACKER_HOST}:{TRACKER_PORT}")
    await asyncio.Event().wait()


async def main() -> None:
    logger.info("Initializing database...")
    await init_db()

    if settings.PROXY_URL:
        logger.info(f"Using proxy: {settings.PROXY_URL.split('@')[-1]}")
        session = ProxiedSession(settings.PROXY_URL)
    else:
        session = AiohttpSession()

    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(AuthMiddleware())

    dp.include_router(client_router)
    dp.include_router(admin_router)
    dp.include_router(worker_router)
    dp.include_router(common_router)

    await asyncio.gather(
        run_bot(bot, dp),
        run_tracker(bot),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped.")
