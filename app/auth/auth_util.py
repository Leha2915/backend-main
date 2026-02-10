"""
This module provides utilities for authentication.
"""
import hashlib
import os
from datetime import datetime, timezone, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_user import User
from app.db.models_auth import RefreshTokens

from passlib.context import CryptContext

# This allows for easier testing as password hashing can now be easily disabled during testing by
# altering this constant.
CRYPT_CONTEXT = CryptContext(
    schemes=["bcrypt"],
    default="bcrypt",
    truncate_error=True
)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"

async def get_username(token: str, db: AsyncSession) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user = payload.get("username")
        if user is None:
            return None

        res = await db.execute(
            select(User).where(User.username == user)
        )
        user = res.scalars().first()
        if user is None:
            return None

        return user.username

    except jwt.InvalidTokenError:
        return None
    except SQLAlchemyError:
        return None


def create_token(username: str, expire_minutes: int) -> str | None:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "username": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def hash_password(password: str) -> str:
    return CRYPT_CONTEXT.hash(secret=password)


async def check_credentials(username: str, cleartext_password: str, db: AsyncSession) -> bool:
    try:
        res = await db.execute(
            select(User).where(User.username == username)
        )
        user = res.scalars().first()

        if user is None:
            return False

        return CRYPT_CONTEXT.verify(secret=cleartext_password, hash=user.password, scheme="bcrypt")
    except SQLAlchemyError:
        return False


def sha_256(string: str) -> str:
    return hashlib.sha256(string.encode()).hexdigest()


async def get_refresh_token(username: str, db: AsyncSession) -> str | None:
    try:
        res = await db.execute(
            select(RefreshTokens).where(RefreshTokens.username == username)
        )
        token = res.scalars().first()
        if token is None:
            return None

        token_str = token.refresh_token
        return token_str

    except SQLAlchemyError:
        return None


async def compare_refresh_to_db(username: str, refresh_token: str, db: AsyncSession) -> bool:
    token_from_db = await get_refresh_token(username, db)
    if token_from_db is None:
        return False

    return sha_256(refresh_token) == token_from_db


async def update_refresh_token(username: str, refresh_token: str, db: AsyncSession) -> None:
    try:
        await db.execute(
            insert(RefreshTokens)
            .values(username=username, refresh_token=sha_256(refresh_token))
            .on_conflict_do_update(
                index_elements=['username'],
                set_={'refresh_token': sha_256(refresh_token)}
            )
        )
        await db.commit()
        return None

    except SQLAlchemyError:
        await db.rollback()
        return None


