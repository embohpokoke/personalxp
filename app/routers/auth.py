from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import (
    SessionIdentity,
    create_session_token,
    require_agent,
    require_session,
    verify_pin,
)
from app.config import Settings, get_settings
from app.db import get_pool
from app.schemas import AuthResponse, LoginRequest, UserPublic


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def user_public(row: asyncpg.Record) -> UserPublic:
    return UserPublic(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        role=row["role"],
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, email, pin_hash, role
            FROM users
            ORDER BY id ASC
            LIMIT 1
            """
        )

    if row is None or not verify_pin(payload.pin, row["pin_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid PIN",
        )

    token = create_session_token(row["id"], row["role"], payload.entered_by, settings)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.jwt_ttl_hours * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    return AuthResponse(user=user_public(row), entered_by=payload.entered_by)


@router.post("/logout")
async def logout(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    response.delete_cookie(
        settings.session_cookie_name,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    return {"message": "logged out"}


@router.get("/me", response_model=AuthResponse)
async def me(
    identity: Annotated[SessionIdentity, Depends(require_session)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AuthResponse:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, email, role
            FROM users
            WHERE id = $1
            """,
            identity.user_id,
        )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid session",
        )
    return AuthResponse(user=user_public(row), entered_by=identity.entered_by)


@router.get("/agent-check")
async def agent_check(_: Annotated[object, Depends(require_agent)]) -> dict[str, str]:
    return {"status": "ok"}
