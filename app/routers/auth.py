from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends

from app.db import get_db
from app.schemas.schemas_auth import RefreshRequest, TokenPair, UserLogin

from fastapi import Request

from app.auth.auth_util import check_credentials, create_token, get_username, update_refresh_token, \
    compare_refresh_to_db

USER_OR_PASSWORD_INCORRECT_MSG = "Username or password incorrect"

LOGIN_EXP_MINUTES = 10
REFRESH_EXP_MINUTES = 480

router = APIRouter(
    prefix="/auth-new",
    tags=["auth-new"]
)

def _get_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return None

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0], parts[1].strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


async def get_current_username(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    """
    Das hier benutzen, um den Username aus dem Bearer Access-Token auszulesen.
    Dafür einfach username: str = Depends(get_current_username) zur Methodensignatur im Endpoint hinzufügen.
    Falls der username None ist, muss das entsprechend gehandelt werden. Es bedeutet, dass der Nutzer nicht
    eingeloggt ist.
    """
    access_token = _get_bearer_token(request)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    access_name = await get_username(access_token, db)
    if access_name is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return access_name

# ───────────────────────── Endpoints ────────────────────────────

@router.post("/login", status_code=200, response_model=TokenPair)
async def login(
        payload: UserLogin,
        db: AsyncSession = Depends(get_db),
):
    if not await check_credentials(payload.username, payload.password, db):
        raise HTTPException(401, detail=USER_OR_PASSWORD_INCORRECT_MSG)

    access_token = create_token(payload.username, LOGIN_EXP_MINUTES)
    refresh_token = create_token(payload.username, REFRESH_EXP_MINUTES)
    await update_refresh_token(payload.username, refresh_token, db)

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", status_code=200, response_model=TokenPair)
async def refresh_tokens(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    refresh_name = await get_username(payload.refresh_token, db)
    if refresh_name is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if not await compare_refresh_to_db(refresh_name, payload.refresh_token, db):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access_token = create_token(refresh_name, LOGIN_EXP_MINUTES)
    new_refresh_token = create_token(refresh_name, REFRESH_EXP_MINUTES)
    await update_refresh_token(refresh_name, new_refresh_token, db)

    return TokenPair(access_token=new_access_token, refresh_token=new_refresh_token)
