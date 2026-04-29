from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import secrets
from typing import Annotated, Any, Literal

import bcrypt
from fastapi import Header, HTTPException, Request, status
import jwt

from app.config import Settings, get_settings


EnteredBy = Literal["primary", "secondary"]


@dataclass(frozen=True)
class SessionIdentity:
    user_id: int
    role: str
    entered_by: EnteredBy | None = None


@dataclass(frozen=True)
class AgentIdentity:
    name: Literal["hermes", "openclaw"]


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
    except ValueError:
        return False


def create_session_token(
    user_id: int,
    role: str,
    entered_by: EnteredBy | None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "entered_by": entered_by,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.jwt_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_session_token(token: str, settings: Settings | None = None) -> SessionIdentity:
    settings = settings or get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        entered_by = payload.get("entered_by")
        if entered_by not in ("primary", "secondary", None):
            entered_by = None
        return SessionIdentity(
            user_id=int(payload["sub"]),
            role=str(payload.get("role", "owner")),
            entered_by=entered_by,
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid session",
        ) from exc


def require_session(
    request: Request,
) -> SessionIdentity:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing session",
        )
    return decode_session_token(token, settings)


def require_agent(
    x_agent_name: Annotated[str | None, Header()] = None,
    x_agent_key: Annotated[str | None, Header()] = None,
) -> AgentIdentity:
    settings = get_settings()
    key_by_agent = {
        "hermes": settings.agent_key_hermes,
        "openclaw": settings.agent_key_openclaw,
    }

    agent_name = (x_agent_name or "").strip().lower()
    expected_key = key_by_agent.get(agent_name)
    if not expected_key or not x_agent_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid agent credentials",
        )

    if not secrets.compare_digest(
        expected_key.encode("utf-8"),
        x_agent_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid agent credentials",
        )

    return AgentIdentity(name=agent_name)  # type: ignore[arg-type]
