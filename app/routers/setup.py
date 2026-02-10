from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException
from openai import AuthenticationError, OpenAIError
from pydantic import BaseModel

from app.routers.util.utils import _client

router = APIRouter()
logger = logging.getLogger(__name__)

class KeyTestRequest(BaseModel):
    OPENAI_API_KEY: str
    base_url: str
class ModelListRequest(BaseModel):
    OPENAI_API_KEY: str
    base_url: str


@router.post("/models", response_model=List[str])
async def list_models(req: ModelListRequest):

    try:
        client = _client(req.OPENAI_API_KEY, req.base_url)

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
    try:
        client = _client(req.OPENAI_API_KEY, req.base_url)
        async for _ in client.models.list():
            return {"ok": True}
        return {"ok": False, "reason": "No models returned"}
    except AuthenticationError:
        return {"ok": False, "reason": "Invalid API key"}
    except OpenAIError as e:
        return {"ok": False, "reason": str(e)}
    except Exception:
        return {"ok": False, "reason": "Unexpected error occurred"}