from dataclasses import dataclass
from typing import Literal

import asyncpg
from fastapi import HTTPException, Request, status

from app.auth import AgentIdentity, SessionIdentity, decode_session_token, require_agent
from app.config import get_settings


@dataclass(frozen=True)
class Actor:
    kind: Literal["web", "agent"]
    user_id: int
    entered_by: str | None
    source_agent: str


async def get_shared_user_id(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT id FROM users ORDER BY id ASC LIMIT 1")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="shared user is not configured",
        )
    return int(user_id)


def session_from_request(request: Request) -> SessionIdentity | None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    return decode_session_token(token, settings)


def agent_from_request(request: Request) -> AgentIdentity | None:
    agent_name = request.headers.get("X-Agent-Name")
    agent_key = request.headers.get("X-Agent-Key")
    if not agent_name and not agent_key:
        return None
    return require_agent(agent_name, agent_key)


async def actor_from_request(request: Request, pool: asyncpg.Pool) -> Actor:
    session = session_from_request(request)
    if session is not None:
        return Actor(
            kind="web",
            user_id=session.user_id,
            entered_by=session.entered_by,
            source_agent="web",
        )

    agent = agent_from_request(request)
    if agent is not None:
        return Actor(
            kind="agent",
            user_id=await get_shared_user_id(pool),
            entered_by=None,
            source_agent=agent.name,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="authentication required",
    )
