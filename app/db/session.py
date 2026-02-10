from __future__ import annotations
from typing import AsyncGenerator
from .models_user import User
from sqlalchemy import select, text

from app.auth.auth_util import hash_password

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import POSTGRES_URL
from .base import Base  # noqa: F401


# ───────────────────────── engine & session factory ─────────────────────────
engine = create_async_engine(POSTGRES_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: liefert pro Request eine AsyncSession."""
    async with async_session() as session:
        yield session


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_session

# ───────────────────────── schema initialisation ────────────────────────────
async def init_models() -> None:
    """
    Legt alle in Base.metadata registrierten Tabellen an,
    sofern sie noch nicht existieren. Kann gefahrlos mehrfach
    ausgeführt werden (idempotent).
    """
    async with engine.begin() as conn:
        # NUR WÄHREND ENTWICKLUNG, LÖSCHT ALLE DATEN!
        # await conn.execute(text("DROP SCHEMA public CASCADE"))
        # await conn.execute(text("CREATE SCHEMA public"))

        # create_all ist synchron → via run_sync ausführen
        await conn.run_sync(Base.metadata.create_all)

    #TEST-ANMELDUNG TODO:REMOVE
    async with async_session() as session:
        # Default-User anlegen (wenn nicht vorhanden)
        res = await session.execute(select(User).where(User.username == "admin"))
        if not res.scalar():
            user = User(username="admin", password=hash_password("test123"))
            session.add(user)
            await session.commit()
