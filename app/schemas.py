from typing import Literal

from pydantic import BaseModel, Field


EnteredBy = Literal["primary", "secondary"]


class LoginRequest(BaseModel):
    pin: str = Field(min_length=1, max_length=64)
    entered_by: EnteredBy | None = None


class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    role: str


class AuthResponse(BaseModel):
    user: UserPublic
    entered_by: EnteredBy | None = None
