from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Пользователи бота — воркеры и админы."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="worker", nullable=False)
    # worker | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relations
    domains: Mapped[List["Domain"]] = relationship(back_populates="worker", lazy="selectin")
    landings: Mapped[List["Landing"]] = relationship(back_populates="worker", lazy="selectin")
    links: Mapped[List["Link"]] = relationship(back_populates="worker", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User tg_id={self.tg_id} role={self.role}>"


class Domain(Base):
    """Домены воркеров, привязанные к IP сервера."""
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # IP который должен быть прописан в DNS
    expected_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    # Проверен ли DNS
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    worker_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relations
    worker: Mapped[Optional["User"]] = relationship(back_populates="domains")
    landings: Mapped[List["Landing"]] = relationship(back_populates="domain", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Domain {self.domain} verified={self.is_verified}>"


class Landing(Base):
    """Лендинги — привязываются к домену и воркеру."""
    __tablename__ = "landings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # URL или путь к лендингу
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    worker_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    domain_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("domains.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relations
    worker: Mapped[Optional["User"]] = relationship(back_populates="landings")
    domain: Mapped[Optional["Domain"]] = relationship(back_populates="landings")
    links: Mapped[List["Link"]] = relationship(back_populates="landing", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Landing {self.name}>"


class Link(Base):
    """Реф-ссылки воркеров."""
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    # Описание / название ссылки (задаёт воркер)
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    worker_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    landing_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("landings.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relations
    worker: Mapped[Optional["User"]] = relationship(back_populates="links")
    landing: Mapped[Optional["Landing"]] = relationship(back_populates="links")
    stats: Mapped[List["Stat"]] = relationship(back_populates="link", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Link slug={self.slug}>"


class Application(Base):
    """Заявки от пользователей."""
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # Воркер через чью реф-ссылку пришёл (если есть)
    worker_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Application tg_id={self.tg_id}>"


class Stat(Base):
    """События по ссылкам: клик или лид."""
    __tablename__ = "stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("links.id", ondelete="SET NULL"), nullable=True
    )
    # click | lead
    event: Mapped[str] = mapped_column(String(16), nullable=False, default="click")
    # Можно хранить IP или другую мету
    meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relations
    link: Mapped[Optional["Link"]] = relationship(back_populates="stats")

    def __repr__(self) -> str:
        return f"<Stat event={self.event} link_id={self.link_id}>"
