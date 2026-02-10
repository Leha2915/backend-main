from __future__ import annotations

import os, hashlib, shutil
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.encryption_service import EncryptionService, get_encryption_service
from app.db.models_chat import InterviewSession
from app.db.models_project import Project
from app.db.session import get_sessionmaker
from app.interview import SessionManager
from app.interview.interview_tree.tree_utils import TreeUtils
from app.models import AssistantResponse
from app.routers.util.utils import _client
from app.llm.template_store import TEMPLATES
from app.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    template_name: str = Field(
        default="default",
        description=f"Key from template_store.TEMPLATES (choices: {list(TEMPLATES)})",
    )
    template_vars: Dict[str, Any] = Field(
        default_factory=dict,
        description="Values for {{placeholders}} in the template",
    )
    projectSlug: Optional[str] = Field(
        default=None, description="Project slug to select the OpenAI key"
    )
    session_id: Optional[str] = None
    stimulus: str
    message: str


@router.post("/interview/chat", response_model=AssistantResponse, response_model_exclude_none=True)
async def interview_chat(
    req: ChatCompletionRequest,
    enc: EncryptionService = Depends(get_encryption_service),
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
) -> AssistantResponse:
    async with sessionmaker() as db:
        proj = await db.scalar(select(Project).where(Project.slug == req.projectSlug))
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        try:
            api_key = enc.decrypt(proj.api_key)
        except Exception:
            api_key = proj.api_key

        project_data = Project(
            id=proj.id,
            topic=proj.topic,
            stimuli=proj.stimuli,
            api_key=api_key,
            base_url=proj.base_url,
            model=proj.model,
            n_values_max=proj.n_values_max,
            min_nodes=proj.min_nodes,
            max_retries=proj.max_retries,
        )

        interview_session, session_id = await SessionManager.setup(
            project_data=project_data,
            db_session=db,
            session_id=req.session_id,
        )

    client = _client(api_key, project_data.base_url)

    response: Dict[str, Any] = await interview_session.handle_input(
        req.stimulus,
        message=req.message,
        client=client,
        model=project_data.model,
        template_vars={"template_name": req.template_name,
                       **req.template_vars},
    )

    trees = [chat.tree for chat in interview_session.chat_session_handlers]
    merged_tree = TreeUtils.merge_trees_with_topic(project_data.topic, trees)
    response["Tree"] = json.loads(TreeUtils.to_json(merged_tree))

    if isinstance(response.get("Next"), dict):
        response["Next"]["session_id"] = session_id
    else:
        response["session_id"] = session_id

    snapshot = interview_session.to_dict()

    async with sessionmaker() as dbw:
        stmt = select(InterviewSession).where(
            InterviewSession.id == interview_session.session_id)
        row = await dbw.execute(stmt)
        db_session_obj = row.scalar_one_or_none()
        if not db_session_obj:
            db_session_obj = InterviewSession(
                id=interview_session.session_id,
                chat_data=None,
                project_id=project_data.id,
                created_at=datetime.now(),
            )
            dbw.add(db_session_obj)
        db_session_obj.chat_data = snapshot
        await dbw.commit()

    return AssistantResponse(**response)


@router.get("/interview/test")
def test_route():
    """Simple test route to verify router is mounted."""
    return {"status": "ok"}
