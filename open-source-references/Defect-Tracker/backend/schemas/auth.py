from uuid import UUID
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MeResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    roles: list[str]
    scopes: list[str]
