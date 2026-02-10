# backend/main.py
"""
FastAPI backend that calls OpenAI with the new `client.responses.parse`
helper for Structured Outputs, and logs the Function-Tree sent from the frontend.
"""
from __future__ import annotations
import logging
import os
from typing import List

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas_user import UserAuthRequest
from .db.session import get_db, init_models

from .llm.template_store import TEMPLATES

from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, save_stimuli, users, auth, project, setup, voice_tts, voice_stt, interview_sessions, load_chats, r2_proxy, onboarding, user_logging, export

# ───────────────────────── logging ──────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _get_allowed_origins() -> list[str]:
    default_origins = [
        "http://localhost:3000",
        "https://ladderchat.k8s.iism.kit.edu",
    ]
    configured_origins = os.getenv("CORS_ORIGINS", "")
    origins = [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    for origin in default_origins:
        if origin not in origins:
            origins.append(origin)
    return origins


# ───────────────────────── FastAPI app ──────────────────────────────────────
app = FastAPI(title="Stateless LLM Backend (Structured Outputs v2)")
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(project.router)
app.include_router(chat.router)
app.include_router(setup.router)
app.include_router(voice_tts.router)
app.include_router(voice_stt.router)
app.include_router(interview_sessions.router)
app.include_router(load_chats.router)
app.include_router(save_stimuli.router)
app.include_router(r2_proxy.router)
app.include_router(onboarding.router)
app.include_router(user_logging.router)
app.include_router(export.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────── DB-Schema sicherstellen ──────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    """Stellt sicher, dass alle benötigten Tabellen existieren."""
    await init_models()

# ───────────────────────── routes ───────────────────────────────────────────
@app.get("/templates", response_model=List[str])
async def list_templates() -> List[str]:
    logger.info("GET /templates")
    return list(TEMPLATES)

# ───────────────────────── User-Endpoints ────────────────────────────

@app.post("/auth")
async def check_credentials(
    payload: UserAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(status_code=404, detail="/auth route was removed! Use /auth-new/login route!")


@app.post("/admin/full-reset")
async def full_reset():
    if os.getenv("ENABLE_FULL_RESET_ENDPOINT", "false").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Not found")

    from .db.base import Base
    from .db.session import engine

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.run_sync(Base.metadata.create_all)

    return {"status": "ok", "message": "Full structure reset"}


@app.post("/debug/payload-check")
async def debug_payload_check(req: dict):
    """Debug-Endpoint zur Überprüfung des Request-Payloads"""
    required_fields = ["template_name", "template_vars", "messages", "model"]

    missing_fields = [field for field in required_fields if field not in req]

    auth_option1 = "projectSlug" in req
    auth_option2 = "base_url" in req and "OPENAI_API_KEY" in req

    return {
        "valid": len(missing_fields) == 0 and (auth_option1 or auth_option2),
        "missing_required_fields": missing_fields,
        "auth_valid": auth_option1 or auth_option2,
        "received_fields": list(req.keys())
    }

# ───────────────────────── dev entrypoint ───────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    host, port = "0.0.0.0", 8000
    logger.info("Starting dev server on http://%s:%d", host, port)
    uvicorn.run("main:app", host=host, port=port, reload=True)

