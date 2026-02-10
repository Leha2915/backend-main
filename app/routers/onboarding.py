from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_chat import InterviewSession
from app.db.models_project import Project
from app.db.session import get_db
from app.auth.encryption_service import EncryptionService, get_encryption_service
from app.routers.util.utils import _client

import json

from app.llm.template_store import render_template
from app.llm.structured_output_manager import StructuredOutputManager, OutputFormat

router = APIRouter()
logger = logging.getLogger(__name__)


class OnboardingChatRequest(BaseModel):
    project_slug: Optional[str] = Field(default=None, description="Project slug to select the OpenAI key")
    session_id: Optional[str] = None
    message: str
    path: str
    finish: bool
    template: str = "onboardingBasic"

class OnboardingChatAnswer(BaseModel):
    message: str

@router.post("/onboarding-chat", response_model=OnboardingChatAnswer)
async def chat_onboarding(
    req: OnboardingChatRequest,
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
    ):

    project_stmt = select(Project).where(Project.slug == req.project_slug)
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()

    project_data = Project(
        id=project.id,
        topic=project.topic,
        stimuli=project.stimuli,
        base_url=project.base_url,
        model=project.model,
        n_values_max=project.n_values_max,
        max_retries=project.max_retries,
    )

    try:
        api_key = enc.decrypt(project.api_key)
    except Exception:
        api_key = project.api_key


    client = _client(api_key, project_data.base_url)


    # Initialize LLM client
    from app.llm.client import LlmClient
    llm_client = LlmClient(client, project_data.model)
    

    print(req.finish)
    prompt_vars = {
        "topic": "Onboarding",
        "active_stimulus": "Onboarding",
        "active_node_label": "None",
        "active_node_content": "None",
        "current_path": req.path,
        "interview_stage": "onboarding",
        "last_user_response": req.message,
        "parent_context": "None",
        "test" : req.finish
    }
    
    system_prompt = render_template(req.template, **prompt_vars)

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    json_schema = {
        "type": "object",
        "properties": {
            "NextMessage": {"type": "string"},
        },
        "required": ["NextMessage"]
    }

    try:

        response_content = await llm_client.query_with_structured_output(
            messages=messages,
            schema=json_schema,
            temperature=0.4
        )
        
    except Exception as e:
        print (f"LLM API call failed: {e}")
        raise e
    
    try:
        parsed_data = json.loads(response_content)
    except json.JSONDecodeError as parse_error:
        logger.error(
        f"JSON parsing failed: {parse_error}")
        raise parse_error


    #stmt = select(InterviewSession).where(
    #    InterviewSession.id == req.session_id)
    #result = await db.execute(stmt)
    #interview_session = result.scalar_one_or_none()


    return OnboardingChatAnswer(message=parsed_data["Next"]["NextQuestion"])
