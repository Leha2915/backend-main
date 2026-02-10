from __future__ import annotations
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class RefreshTokens(Base):
    __tablename__ = "refresh_tokens"
    username: Mapped[str] = mapped_column(ForeignKey("users.username"), nullable=False, primary_key=True)
    refresh_token: Mapped[str] = mapped_column(Text)

