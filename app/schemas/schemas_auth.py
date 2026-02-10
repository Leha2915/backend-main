from pydantic import BaseModel, constr


class UserLogin(BaseModel):
    username: constr(min_length=3, max_length=80)
    password: constr(min_length=3, max_length=255)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthRequest(BaseModel):
    access_token: str
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str

