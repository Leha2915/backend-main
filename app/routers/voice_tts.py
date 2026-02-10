import httpx
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.encryption_service import EncryptionService, get_encryption_service
from app.db.models_project import Project
from app.db.session import get_db

router = APIRouter()

DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
ELEVEN_BASE_URL = "https://api.elevenlabs.io/v1"

DEFAULT_MODEL_ID = "eleven_turbo_v2_5"
SUPPORTED_MULTILINGUAL_MODELS = {"eleven_turbo_v2_5", "eleven_multilingual_v2"}
DEFAULT_OPTIMIZE_STREAMING_LATENCY = 4
DEFAULT_OUTPUT_FORMAT = "mp3_22050_32"
DEFAULT_VOICE_SETTINGS = {"stability": 0.3, "similarity_boost": 0.75}

GERMAN_VOICE_ID = "ErXwobaYiN019PkySvjV"


def _norm_lang_code(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return None
    return lang.lower().split("-")[0] or None


def _pick_voice_id(language_code: Optional[str], requested_voice_id: Optional[str]) -> str:
    if requested_voice_id:
        return requested_voice_id
    if _norm_lang_code(language_code) == "de":
        return GERMAN_VOICE_ID
    return DEFAULT_VOICE_ID


def _elevenlabs_client(api_key: str) -> httpx.AsyncClient:
    headers = {"xi-api-key": api_key} if api_key else {}
    return httpx.AsyncClient(
        base_url=ELEVEN_BASE_URL,
        headers=headers,
        timeout=httpx.Timeout(30.0, read=60.0, connect=10.0),
    )


async def _get_eleven_api_key(
    project_slug: str,
    db: AsyncSession,
    enc: EncryptionService,
    error_detail: str,
) -> str:
    res = await db.execute(select(Project).where(Project.slug == project_slug))
    project = res.scalars().first()
    if not project:
        raise HTTPException(status_code=400, detail=error_detail)
    api_key = enc.decrypt(project.elevenlabs_api_key)
    if not api_key:
        raise HTTPException(status_code=400, detail=error_detail)
    return api_key


@router.post("/tts/test")
async def tts_test(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):
    project_slug: str = body.get("projectSlug", "")
    api_key = await _get_eleven_api_key(
        project_slug, db, enc, error_detail="TTS not configured on server"
    )

    payload = {"text": "", "model_id": DEFAULT_MODEL_ID}
    endpoint = f"/text-to-speech/{DEFAULT_VOICE_ID}/stream"

    async with _elevenlabs_client(api_key) as client:
        try:
            r = await client.post(endpoint, json=payload, headers={"Accept": "audio/mpeg"})
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)

    return {"ok": True}


@router.post("/tts/single")
async def tts_one_shot(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):
    project_slug: str = body.get("projectSlug", "")
    api_key = await _get_eleven_api_key(
        project_slug, db, enc, error_detail="TTS not configured in project"
    )

    text: str = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    language_code: Optional[str] = body.get("language_code")
    requested_voice_id: Optional[str] = body.get("voice_id")
    model_id: str = body.get("model_id") or DEFAULT_MODEL_ID
    output_format: str = body.get("output_format") or DEFAULT_OUTPUT_FORMAT
    voice_settings: Dict[str, Any] = body.get("voice_settings") or DEFAULT_VOICE_SETTINGS

    if language_code and _norm_lang_code(language_code) != "en" and model_id not in SUPPORTED_MULTILINGUAL_MODELS:
        model_id = "eleven_turbo_v2_5"

    voice_id: str = _pick_voice_id(language_code, requested_voice_id)

    payload: Dict[str, Any] = {"text": text, "model_id": model_id, "output_format": output_format}
    if voice_settings:
        payload["voice_settings"] = voice_settings

    qs = f"?language_code={language_code}" if language_code else ""
    endpoint = f"/text-to-speech/{voice_id}{qs}"

    async with _elevenlabs_client(api_key) as client:
        try:
            r = await client.post(endpoint, json=payload, headers={"Accept": "audio/mpeg"})
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

        return Response(content=r.content, media_type="audio/mpeg")


@router.post("/tts/stream")
async def tts_stream(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):
    project_slug: str = body.get("projectSlug", "")
    api_key = await _get_eleven_api_key(
        project_slug, db, enc, error_detail="TTS not configured in project"
    )

    text: str = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Missing text")

    language_code: Optional[str] = body.get("language_code")
    requested_voice_id: Optional[str] = body.get("voice_id")
    model_id: str = body.get("model_id") or DEFAULT_MODEL_ID
    output_format: str = body.get("output_format") or DEFAULT_OUTPUT_FORMAT
    optimize_streaming_latency: int = (
        body.get("optimize_streaming_latency") or DEFAULT_OPTIMIZE_STREAMING_LATENCY
    )
    voice_settings: Dict[str, Any] = body.get("voice_settings") or DEFAULT_VOICE_SETTINGS

    if language_code and _norm_lang_code(language_code) != "en" and model_id not in SUPPORTED_MULTILINGUAL_MODELS:
        model_id = "eleven_turbo_v2_5"

    voice_id: str = _pick_voice_id(language_code, requested_voice_id)

    payload: Dict[str, Any] = {
        "text": text,
        "model_id": model_id,
        "output_format": output_format,
        "optimize_streaming_latency": optimize_streaming_latency,
    }
    if voice_settings:
        payload["voice_settings"] = voice_settings

    qs = f"?language_code={language_code}" if language_code else ""
    endpoint = f"/text-to-speech/{voice_id}/stream{qs}"

    async def gen() -> AsyncIterator[bytes]:
        async with _elevenlabs_client(api_key) as client:
            try:
                async with client.stream(
                    "POST", endpoint, json=payload, headers={"Accept": "audio/mpeg"}
                ) as r:
                    if r.status_code >= 400:
                        text_bytes = await r.aread()
                        raise HTTPException(
                            status_code=r.status_code,
                            detail=text_bytes.decode("utf-8", "ignore"),
                        )
                    async for chunk in r.aiter_bytes():
                        if chunk:
                            yield chunk
            except httpx.HTTPError as e:
                raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    return StreamingResponse(gen(), media_type="audio/mpeg")
