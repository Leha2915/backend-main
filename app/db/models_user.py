# backend/app/db/models_user.py
from __future__ import annotations
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # neu: eindeutiger Username
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)

    # Klartext-Passwort
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
