from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.encryption_service import get_encryption_service
from app.db.models_chat import InterviewSession as InterviewSession
from app.db.models_project import Project
from app.db.session import get_db
from app.interview.session.interview_session_manager import InterviewSessionManager
from app.interview.interview_tree.tree_utils import TreeUtils


router = APIRouter()
logger = logging.getLogger(__name__)


class Role(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class HistoryLoadRequest(BaseModel):
    projectSlug: Optional[str] = Field(
        default=None, description="Project slug")
    session_id: str


class ChatItem(BaseModel):
    content: str
    role: Role
    node_ids: Optional[List[str]] = None
    created_ns: Optional[List[str]] = None


class History(BaseModel):
    content: List[List[ChatItem]]
    order: List[str]
    finished: List[str]
    tree: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class ProjectDTO:
    id: int
    topic: str
    stimuli: List[str]
    api_key: str
    base_url: Optional[str]
    model: Optional[str]
    n_values_max: Optional[int]
    n_stimuli: Optional[int]
    max_retries: Optional[int]


@router.post(
    "/interview/load",
    response_model=History,
    response_model_exclude_none=True,
)
async def load_interview(
    req: HistoryLoadRequest,
    db: AsyncSession = Depends(get_db),
) -> History:
    interview_session = await db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == req.session_id)
    )
    if not interview_session:
        raise HTTPException(status_code=404, detail="Interview not found")

    project = await db.scalar(select(Project).where(Project.slug == req.projectSlug))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        key = get_encryption_service().decrypt(project.api_key)
    except Exception:
        key = project.api_key

    project_dto = ProjectDTO(
        id=project.id,
        topic=project.topic,
        stimuli=project.stimuli,
        api_key=key,
        base_url=project.base_url,
        model=project.model,
        n_values_max=project.n_values_max,
        n_stimuli=getattr(project, "n_stimuli", None),
        max_retries=project.max_retries,
    )

    ordered_stimuli = interview_session.stimuli_order or []
    n = project_dto.n_stimuli or len(ordered_stimuli)
    top_stimuli = ordered_stimuli[:n]

    if not interview_session.chat_data:
        return History(content=[], order=top_stimuli, finished=[], tree=None)

    interview = InterviewSessionManager.from_dict(interview_session.chat_data)

    histories: List[List[ChatItem]] = []
    finished: List[str] = []

    for stimulus in top_stimuli:
        chat = interview.get_chat_by_stimulus(stimulus)
        if not chat:
            continue
        typed_history: List[ChatItem] = []
        for m in chat.chat_history:
            print(m.get("node_ids"), type(m.get("node_ids")))
            typed_history.append(
                ChatItem(
                    content=m["content"],
                    role=Role(m["role"]),
                    node_ids=m.get("node_ids"),
                    created_ns=m.get("created_ns"),
                )
            )
        histories.append(typed_history)
        if getattr(chat, "is_finished", False):
            finished.append(chat.stimulus)

    trees = [c.tree for c in interview.chat_session_handlers]
    merged_tree = TreeUtils.merge_trees_with_topic(project_dto.topic, trees)
    tree_json = json.loads(TreeUtils.to_json(merged_tree))

    return History(content=histories, order=top_stimuli, finished=finished, tree=tree_json)


class ChatMessagesRequest(BaseModel):
    session_id: str
    projectSlug: Optional[str] = Field(
        default=None, description="Project slug")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    limit: int = Field(default=500, ge=1, le=5000,
                       description="Pagination limit")


class ChatMessageItem(BaseModel):
    role: Role
    content: str
    chat_index: int
    message_index: int
    global_index: int
    node_ids: List[str] = Field(default_factory=list)
    created_ns: List[str] = Field(default_factory=list)


class ChatMessagesResponse(BaseModel):
    messages: List[ChatMessageItem]
    total_messages: int


@router.post(
    "/interview/all_chat_messages",
    response_model=ChatMessagesResponse,
    response_model_exclude_none=True,
)
async def list_all_chat_messages(
    req: ChatMessagesRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatMessagesResponse:
    interview_session = await db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == req.session_id)
    )
    if not interview_session:
        raise HTTPException(
            status_code=404, detail="Interview session not found")

    if not interview_session.chat_data:
        return ChatMessagesResponse(messages=[], total_messages=0)

    interview = InterviewSessionManager.from_dict(interview_session.chat_data)

    flat: List[ChatMessageItem] = []
    for chat_index, handler in enumerate(interview.chat_session_handlers):
        for message_index, m in enumerate(handler.chat_history):
            flat.append(
                ChatMessageItem(
                    role=Role(m["role"]),
                    content=m["content"],
                    chat_index=chat_index,
                    message_index=message_index,
                    global_index=len(flat),
                    node_ids=m.get("node_ids", []),
                )
            )

    start = req.offset
    end = req.offset + req.limit

    return ChatMessagesResponse(messages=flat[start:end], total_messages=len(flat))
