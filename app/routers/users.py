from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.auth.auth_util import hash_password
from app.db import get_db
from app.schemas.schemas_user import UserCreate, UserOut
from app.db.models_user import User

from fastapi import Depends, HTTPException

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.post("/create", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    res = await db.execute(
        select(User).where(User.username == payload.username)
    )
    if res.scalar():
        raise HTTPException(status_code=409, detail="Username already taken")

    new_user = User(username=payload.username, password=hash_password(payload.password))
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user
