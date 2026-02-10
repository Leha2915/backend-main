from __future__ import annotations

import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException
from openai import AuthenticationError, OpenAIError
from pydantic import BaseModel

from app.routers.util.utils import _client

router = APIRouter()
logger = logging.getLogger(__name__)

class KeyTestRequest(BaseModel):
    OPENAI_API_KEY: str | None = None
    base_url: str
class ModelListRequest(BaseModel):
    OPENAI_API_KEY: str | None = None
    base_url: str
class StimuliSuggestRequest(BaseModel):
    role_prompt: str
    model: str
    OPENAI_API_KEY: str | None = None
    base_url: str = "https://api.openai.com/v1"


def _resolve_openai_key(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    return os.getenv("OPENAI_API_KEY_DEFAULT", "").strip()


@router.post("/models", response_model=List[str])
async def list_models(req: ModelListRequest):
    openai_api_key = _resolve_openai_key(req.OPENAI_API_KEY)
    if not openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY missing")
    try:
        client = _client(openai_api_key, req.base_url)

        names: List[str] = []
        try:
            async for m in client.models.list():
                mid = getattr(m, "id", None)
                if mid:
                    names.append(mid)
        except TypeError:
            page = await client.models.list()
            data = getattr(page, "data", [])
            names = [getattr(m, "id", None) for m in data if getattr(m, "id", None)]

        return names

    except AuthenticationError as e:
        print(e)
        raise HTTPException(status_code=401, detail=str(e))
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@router.post("/testOpenaiAPIKey")
async def test_key(req: KeyTestRequest):
    openai_api_key = _resolve_openai_key(req.OPENAI_API_KEY)
    if not openai_api_key:
        return {"ok": False, "reason": "Missing API key and no backend default configured"}
    try:
        client = _client(openai_api_key, req.base_url)
        async for _ in client.models.list():
            return {"ok": True}
        return {"ok": False, "reason": "No models returned"}
    except AuthenticationError:
        return {"ok": False, "reason": "Invalid API key"}
    except OpenAIError as e:
        return {"ok": False, "reason": str(e)}
    except Exception:
        return {"ok": False, "reason": "Unexpected error occurred"}


@router.post("/stimuli/suggest")
async def suggest_stimuli(req: StimuliSuggestRequest):
    openai_api_key = _resolve_openai_key(req.OPENAI_API_KEY)
    if not openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY missing")
    try:
        client = _client(openai_api_key, req.base_url)
        completion = await client.chat.completions.create(
            messages=[{"role": "user", "content": req.role_prompt}],
            model=req.model,
            presence_penalty=0,
            temperature=1,
            response_format={"type": "json_object"},
        )
        return completion.model_dump()
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except OpenAIError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")