import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import auth
from app.config import Settings


def request_with_cookie(name: str, value: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"{name}={value}".encode("utf-8"))],
        }
    )


def test_require_session_reads_configured_cookie_name(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        session_cookie_name="custom_session",
        jwt_secret="test-secret-at-least-32-bytes-long",
    )
    token = auth.create_session_token(7, "owner", "primary", settings)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)

    identity = auth.require_session(request_with_cookie("custom_session", token))

    assert identity.user_id == 7
    assert identity.role == "owner"
    assert identity.entered_by == "primary"


def test_require_session_rejects_missing_configured_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        session_cookie_name="custom_session",
        jwt_secret="test-secret-at-least-32-bytes-long",
    )
    token = auth.create_session_token(7, "owner", None, settings)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)

    with pytest.raises(HTTPException) as exc:
        auth.require_session(request_with_cookie("xp_session", token))

    assert exc.value.status_code == 401
    assert exc.value.detail == "missing session"


def test_require_agent_rejects_unicode_key_without_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(agent_key_hermes="ascii-secret")
    monkeypatch.setattr(auth, "get_settings", lambda: settings)

    with pytest.raises(HTTPException) as exc:
        auth.require_agent(x_agent_name="hermes", x_agent_key="not-it-\u2713")

    assert exc.value.status_code == 401
    assert exc.value.detail == "invalid agent credentials"
