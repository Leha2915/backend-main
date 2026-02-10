from __future__ import annotations

import logging
import json

from datetime import datetime, timezone
from typing import List, Union, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_chat import InterviewSession
from app.db.models_project import Project
from app.db.session import get_db


router = APIRouter()
logger = logging.getLogger(__name__)


class StimuliOrderRequest(BaseModel):
    project_slug: str
    session_id: str
    stimuli_order: List[str]
    user_id: str
    #(e. g. {"laddering":"yes","goals":"yes","change":"no"})
    answers: Optional[Union[str, Dict[str, Any]]] = None

    @field_validator("answers")
    @classmethod
    def parse_answers(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in 'answers'")
        if isinstance(v, dict):
            return v
        raise ValueError("answers must be a JSON string or object")

class SavedOrder(BaseModel):
    status: str

@router.post("/interview/save_order", response_model=SavedOrder)
async def save_stimuli_order(
    data: StimuliOrderRequest,
    db: AsyncSession = Depends(get_db),
):
    project_stmt = select(Project).where(Project.slug == data.project_slug)
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = select(InterviewSession).where(InterviewSession.id == data.session_id)
    result = await db.execute(stmt)
    interview_session = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not interview_session:
        new_session = InterviewSession(
            id=data.session_id,
            project_id=project.id,
            stimuli_order=data.stimuli_order,
            user_id=data.user_id,
            answers=data.answers,
            created_at=now,
            updated_at=now,
        )
        db.add(new_session)
    else:
        interview_session.stimuli_order = data.stimuli_order
        if data.answers is not None:
            interview_session.answers = data.answers
        if hasattr(interview_session, "updated_at"):
            interview_session.updated_at = now

    await db.commit()
    return SavedOrder(status="ok")