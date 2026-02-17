from sqlalchemy import ForeignKey, String, func, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from .base import Base
from app.db.models_user import User
from datetime import datetime

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    topic: Mapped[str] = mapped_column(String(70))
    description: Mapped[str] = mapped_column(String(800))
    stimuli: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    n_stimuli: Mapped[int] = mapped_column(Integer, nullable=False)
    api_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True)
    n_values_max: Mapped[int] = mapped_column(Integer, nullable=True)
    min_nodes: Mapped[int] = mapped_column(Integer, nullable=True)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, nullable=True)
    advanced_voice_enabled: Mapped[bool] = mapped_column(Boolean, nullable=True)
    interview_mode: Mapped[int] = mapped_column(Integer, nullable=True)
    tree_enabled: Mapped[bool] = mapped_column(Boolean, nullable=True)
    elevenlabs_api_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_send: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_limit: Mapped[int] = mapped_column(Integer, nullable=False)

    r2_account_id: Mapped[str] = mapped_column(String(2048), nullable=True)
    r2_access_key_id: Mapped[str] = mapped_column(String(2048), nullable=True)
    r2_secret_access_key: Mapped[str] = mapped_column(String(2048), nullable=True)
    r2_bucket: Mapped[str] = mapped_column(String(2048), nullable=True) 

    language: Mapped[str] = mapped_column(String(10))

    internal_id: Mapped[str] = mapped_column(String(200))

    grouped: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)

    finish_next_title: Mapped[str] = mapped_column(String(500), nullable=True)
    finish_next_body: Mapped[str] = mapped_column(String(2000), nullable=True)
    finish_next_link: Mapped[str] = mapped_column(String(2000), nullable=True)
    info_blocks_en: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    info_blocks_de: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    stt_key: Mapped[str] = mapped_column(String(2048), nullable=True)
    stt_endpoint: Mapped[str] = mapped_column(String(2048), nullable=True)
    stt_provider: Mapped[str] = mapped_column(String(32), nullable=True)

    owner = relationship("User", back_populates="projects")
    User.projects = relationship("Project", back_populates="owner")
