from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text, Index, Boolean, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from .base import Base
import uuid


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    project_id = Column(Integer, index=True, nullable=True)
    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True),
                        server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    chat_data = Column(JSON, nullable=True)
    stimuli_order = Column(JSON, nullable=True)
    answers = Column(JSON, nullable=True)
    events = Column(JSON, nullable=True, default=list)

    chat_sessions = relationship(
        "ChatSession",
        back_populates="interview_session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_interview_sessions_id", "id"),
        Index("ix_interview_sessions_created_at", "created_at"),
    )

    user_id = Column(String, nullable=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    interview_session_id = Column(
        String,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    interview_session = relationship(
        "InterviewSession", back_populates="chat_sessions")

    interactions = relationship(
        "ChatInteraction",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatInteraction(Base):
    __tablename__ = "chat_interactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    system_question = Column(Text)
    user_answer = Column(Text)
    llm_thought = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="interactions")

    __table_args__ = (
        Index("ix_chat_interactions_session_id", "session_id"),
        Index("ix_chat_interactions_created_at", "created_at"),
    )
