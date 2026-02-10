from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import openai
from fastapi import HTTPException

from openai import AsyncOpenAI
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def _client(key: str, base_url: str) -> AsyncOpenAI:

    if not key:
        logger.error("OPENAI_API_KEY missing")
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY missing")

    if not base_url:
        logger.error("Base URL missing")
        raise HTTPException(status_code=400, detail="Base URL is required")

    base_url = base_url.rstrip("/")
    host = (urlparse(str(base_url)).hostname or "").lower()

    default_headers: Dict[str, str] = {}

    if host.endswith("anthropic.com"):
        default_headers["anthropic-version"] = "2023-06-01"
        default_headers["x-api-key"] = key
    
    return AsyncOpenAI(
        api_key=key,
        base_url=base_url,
        default_headers=default_headers
    )