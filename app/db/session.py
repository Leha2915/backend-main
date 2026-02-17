from __future__ import annotations
import os
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

        # Ensure newer nullable project columns also exist on already provisioned DBs.
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS finish_next_title VARCHAR(500)"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS finish_next_body VARCHAR(2000)"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS finish_next_link VARCHAR(2000)"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS stt_provider VARCHAR(32)"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS info_blocks_en JSONB"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS info_blocks_de JSONB"))

    should_seed_admin = os.getenv("SEED_DEFAULT_ADMIN", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    if not should_seed_admin:
        return

    admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "test123")

    async with async_session() as session:
        res = await session.execute(select(User).where(User.username == admin_username))
        if not res.scalar_one_or_none():
            user = User(username=admin_username, password=hash_password(admin_password))
            session.add(user)
            await session.commit()
