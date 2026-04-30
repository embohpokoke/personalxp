from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import re

import asyncpg
from fastapi import FastAPI, Request

from app.config import Settings, get_settings


SCHEMA_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_schema_name(schema: str) -> str:
    if not SCHEMA_NAME_PATTERN.fullmatch(schema):
        raise ValueError("DB_SCHEMA must be a valid PostgreSQL identifier")
    return schema


async def connect(settings: Settings | None = None) -> asyncpg.Pool:
    settings = settings or get_settings()
    db_schema = validate_schema_name(settings.db_schema)

    async def init_connection(conn: asyncpg.Connection) -> None:
        await conn.execute(f"SET search_path TO {db_schema}, public")

    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=5,
        init=init_connection,
        server_settings={"search_path": f"{db_schema},public"},
    )


async def disconnect(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.receipts_dir.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings
    app.state.db_pool = await connect(settings)
    try:
        yield
    finally:
        await disconnect(app.state.db_pool)


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool
