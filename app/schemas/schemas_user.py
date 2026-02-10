# backend/app/schemas_user.py
from datetime import datetime
from pydantic import BaseModel, constr


class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=80)
    password: constr(min_length=3, max_length=255)


class UserAuthRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        orm_mode = True
