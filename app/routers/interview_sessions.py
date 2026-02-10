from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_chat import InterviewSession
from app.db.models_project import Project
from app.db.session import get_db
from app.interview.session.interview_session_manager import InterviewSessionManager
from app.routers.auth import get_current_username

router = APIRouter()
logger = logging.getLogger(__name__)


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_username),
):
    stmt = select(InterviewSession).where(
        InterviewSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
    await db.commit()
    return None


class InterviewSessionSummary(BaseModel):
    id: str
    project_id: int
    stimuli_order: Optional[List[str]] = None
    n_chats: int
    n_messages: int
    started: bool
    finished: bool
    n_finished_chats: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user_id: str = None


class InterviewSessionsResponse(BaseModel):
    topic: str
    total: int
    sessions: List[InterviewSessionSummary]


@router.get(
    "/project/{project_slug}/results",
    response_model=InterviewSessionsResponse,
    response_model_exclude_none=True,
)
async def list_interview_sessions_for_project(
    project_slug: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionsResponse:
    """
    Return all interview sessions for the given project slug with basic metadata and a compact summary per session.
    """
    project = await db.scalar(select(Project).where(Project.slug == project_slug))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = (
        select(InterviewSession)
        .where(InterviewSession.project_id == project.id)
        .order_by(InterviewSession.created_at.desc())
    )
    res = await db.execute(stmt)
    sessions = res.scalars().all()

    summaries: List[InterviewSessionSummary] = []

    for s in sessions:
        n_chats = 0
        n_messages = 0
        started = False
        finished_bool = False
        finished_count = 0

        stimuli_order = getattr(s, "stimuli_order", None) or []

        if getattr(s, "chat_data", None):
            try:
                interview = InterviewSessionManager.from_dict(s.chat_data)
                handlers = list(
                    getattr(interview, "chat_session_handlers", []) or [])
                n_chats = len(handlers)

                n_messages = sum(len(getattr(ch, "chat_history", []) or [])
                                 for ch in handlers)
                started = any(bool(getattr(ch, "chat_history", []))
                              for ch in handlers)

                required_n = getattr(project, "n_stimuli", None) or 0
                if required_n <= 0:
                    required_n = len(stimuli_order) or n_chats

                if stimuli_order:
                    target = set(stimuli_order[:required_n])
                    finished_count = sum(
                        1
                        for ch in handlers
                        if getattr(ch, "is_finished", False)
                        and getattr(ch, "stimulus", None) in target
                    )
                    total_target = len(target)
                else:
                    total_target = min(required_n, n_chats)
                    finished_count = sum(
                        1 for ch in handlers[:total_target] if getattr(ch, "is_finished", False)
                    )

                finished_bool = total_target > 0 and finished_count >= total_target
            except Exception:
                logger.exception(
                    "Failed to parse chat_data for session %s", s.id)
                n_chats = 0
                n_messages = 0
                started = False
                finished_bool = False
                finished_count = 0

        summaries.append(
            InterviewSessionSummary(
                id=s.id,
                project_id=s.project_id or -1,
                stimuli_order=getattr(s, "stimuli_order", None),
                n_chats=n_chats,
                n_messages=n_messages,
                started=started,
                finished=finished_bool,
                n_finished_chats=finished_count,
                created_at=getattr(s, "created_at", None),
                updated_at=getattr(s, "updated_at", None),
                user_id=s.user_id or "xxxxxxxxxxxxxxxxxxxxxxxx",
            )
        )

    return InterviewSessionsResponse(
        topic=project.topic,
        total=len(summaries),
        sessions=summaries,
    )


class SessionInfoResponse(BaseModel):
    id: str
    finished: bool
    n_messages: int
    stimuli_order: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get(
    "/project/{project_slug}/session/{session_id}",
    response_model=SessionInfoResponse,
    response_model_exclude_none=True,
)
async def get_session_info(
    project_slug: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionInfoResponse:
    """
    Return metadata for a single interview session within a project.
    Matches the frontend type 'SessionMeta' (id, finished, n_messages, stimuli_order, created_at, updated_at).
    """
    project = await db.scalar(select(Project).where(Project.slug == project_slug))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    s = await db.scalar(select(InterviewSession).where(InterviewSession.id == session_id))
    if not s:
        raise HTTPException(
            status_code=404, detail="Interview session not found")

    if s.project_id != project.id:
        raise HTTPException(
            status_code=404, detail="Session does not belong to this project")

    n_messages = 0
    finished = False

    if getattr(s, "chat_data", None):
        try:
            interview = InterviewSessionManager.from_dict(s.chat_data)
            handlers = getattr(interview, "chat_session_handlers", []) or []
            n_messages = sum(len(getattr(ch, "chat_history", []) or [])
                             for ch in handlers)
            finished = all(getattr(ch, "is_finished", False)
                           for ch in handlers) if handlers else False
        except Exception:
            n_messages = 0
            finished = False

    return SessionInfoResponse(
        id=s.id,
        finished=finished,
        n_messages=n_messages,
        stimuli_order=getattr(s, "stimuli_order", None),
        created_at=getattr(s, "created_at", None),
        updated_at=getattr(s, "updated_at", None),
    )
