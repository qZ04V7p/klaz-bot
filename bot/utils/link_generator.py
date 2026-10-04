import random
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Link
from config import settings


def generate_slug(length: int = 8) -> str:
    """Генерирует случайный slug из букв и цифр."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


async def create_unique_slug(session: AsyncSession, length: int = 8) -> str:
    """Генерирует slug, гарантированно уникальный в БД."""
    for _ in range(10):
        slug = generate_slug(length)
        exists = await session.scalar(select(Link).where(Link.slug == slug))
        if not exists:
            return slug
    # маловероятно, но на всякий случай увеличиваем длину
    return generate_slug(length + 4)


def build_ref_url(slug: str, domain: str | None = None) -> str:
    """
    Собирает полный URL реф-ссылки.
    Если у воркера есть привязанный домен — использует его,
    иначе базовый URL из конфига.
    """
    base = f"https://{domain}" if domain else settings.BASE_URL.rstrip("/")
    return f"{base}/ref/{slug}"
