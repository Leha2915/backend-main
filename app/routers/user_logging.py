from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_chat import InterviewSession

from app.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

class LogContext(BaseModel):
    session_id: str = Field(alias="sessionId")
    participant_id: Optional[str] = Field(None, alias="participantId")
    project_slug: Optional[str] = Field(None, alias="projectSlug")
    topic_kind: Optional[str] = Field(None, alias="topicKind")
    chat_id: Optional[Union[int, str]] = Field(None, alias="chatId")
    model_config = ConfigDict(populate_by_name=True, extra="allow")

class LogEvent(BaseModel):
    id: str
    type: str
    ts: int
    ctx: LogContext
    value: Optional[str] = Field(None, alias="value")
    draft_id: Optional[str] = Field(None, alias="draftId")
    message_id: Optional[str] = Field(None, alias="messageId")
    text_length: Optional[int] = Field(None, alias="textLength")
    edited: Optional[bool] = None
    composition_ms: Optional[int] = Field(None, alias="compositionMs")
    meta: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(populate_by_name=True, extra="allow")

class LogWriteRequest(BaseModel):
    logs: List[LogEvent]
    model_config = ConfigDict(populate_by_name=True, extra="allow")

@router.post("/logs", response_model=str)
async def chat_onboarding(
    req: LogWriteRequest,
    db: AsyncSession = Depends(get_db),
):
    if not req.logs:
        return "ok"

    session_id = req.logs[0].ctx.session_id
    stmt = select(InterviewSession).where(InterviewSession.id == session_id)
    result = await db.execute(stmt)
    interview_session = result.scalar_one_or_none()

    if not interview_session:
        logger.warning(f"InterviewSession {session_id} not found")
        return "not found"
    
    existing = interview_session.events or []

    new_events = [event.model_dump(by_alias=True, exclude_none=True) for event in req.logs]
    interview_session.events = existing + new_events

    await db.commit()

    return "ok"

@router.get("/logs/{session_id}", response_model=List[Dict[str, Any]])
async def get_session_logs(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(InterviewSession).where(InterviewSession.id == session_id)
    result = await db.execute(stmt)
    interview_session: Optional[InterviewSession] = result.scalar_one_or_none()

    if not interview_session:
        raise HTTPException(status_code=404, detail=f"InterviewSession {session_id} not found")

    return interview_session.events or []