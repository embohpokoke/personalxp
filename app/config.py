from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql:///personal_xp_local"
    db_schema: str = "personal_xp"

    jwt_secret: str = "change-me-local-development-secret-at-least-32-bytes"
    jwt_ttl_hours: int = 720
    session_cookie_name: str = "xp_session"

    agent_key_hermes: str = "change-me"
    agent_key_openclaw: str = "change-me"

    telegram_bot_token: str = ""
    telegram_chat_id_primary: str = ""
    telegram_chat_id_secondary: str = ""
    telegram_dry_run: bool = True

    receipts_dir: Path = Path("./receipts")
    max_receipt_bytes: int = 10_485_760

    env: str = Field(default="local")
    log_level: str = "debug"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
