import os

from fastapi import APIRouter, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from starlette.responses import JSONResponse

from app.db import get_db
from app.schemas.schemas_auth import TokenPair, UserLogin

from fastapi import Request, Response

from app.auth.auth_util import check_credentials, create_token, get_username, update_refresh_token, \
    compare_refresh_to_db

USER_OR_PASSWORD_INCORRECT_MSG = "Username or password incorrect"

SEND_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() in ("1", "true", "yes")
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "none").strip().lower()
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    COOKIE_SAMESITE = "none"

LOGIN_EXP_MINUTES = 10
REFRESH_EXP_MINUTES = 480

router = APIRouter(
    prefix="/auth-new",
    tags=["auth-new"]
)

# ───────────────────────── Cookie-Logic ────────────────────────────

def get_tokens_from_cookie(request: Request) -> TokenPair | None:
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    if access_token is None or refresh_token is None:
        return None

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


def set_cookie(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=SEND_COOKIE_SECURE,
        samesite=COOKIE_SAMESITE
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=SEND_COOKIE_SECURE,
        samesite=COOKIE_SAMESITE
    )


async def get_current_username(
        response: Response,
        access_token: str = Cookie(None),
        refresh_token: str = Cookie(None),
        db: AsyncSession = Depends(get_db)
) -> str:
    """
    Das hier benutzen, um den Username aus den Access-Tokens im Cookie auszulesen.
    Dafür einfach username: str = Depends(get_current_username) zur Methodensignatur im Endpoint hinzufügen.
    Falls der username None ist, muss das entsprechend gehandelt werden. Es bedeutet, dass der Nutzer nicht
    eingeloggt ist.

    Im Frontend muss bei fetch von Endpoints bei denen man Auth braucht credentials: 'include' in den Options gesetzt
    werden, sonst ist der return immer None.
    """
    access_name = await get_username(access_token, db)
    refresh_name = await get_username(refresh_token, db)

    # Both tokens are invalid
    if access_name is None and refresh_name is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Access invalid, but refresh valid
    if access_name is None and refresh_name is not None:
        if not await compare_refresh_to_db(refresh_name, refresh_token, db):
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        new_access_token = create_token(refresh_name, LOGIN_EXP_MINUTES)
        new_refresh_token = create_token(refresh_name, REFRESH_EXP_MINUTES)
        await update_refresh_token(refresh_name, new_refresh_token, db)
        set_cookie(response, new_access_token, new_refresh_token)
        return refresh_name

    # Access valid, refresh invalid
    if access_name is not None and refresh_name is None:
        raise HTTPException(status_code=401, detail="Access revoked for security reasons")

    # Name mismatch
    if access_name != refresh_name:
        raise HTTPException(status_code=401, detail="Token mismatch")

    return access_name

# ───────────────────────── Endpoints ────────────────────────────

@router.post("/login", status_code=200)
async def login(
        payload: UserLogin,
        db: AsyncSession = Depends(get_db),
):
    if not await check_credentials(payload.username, payload.password, db):
        raise HTTPException(401, detail=USER_OR_PASSWORD_INCORRECT_MSG)

    access_token = create_token(payload.username, LOGIN_EXP_MINUTES)
    refresh_token = create_token(payload.username, REFRESH_EXP_MINUTES)
    await update_refresh_token(payload.username, refresh_token, db)

    response = JSONResponse({"message": "Login successful!"})
    set_cookie(response, access_token, refresh_token)

    return response
