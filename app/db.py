from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request

from app.config import Settings, get_settings


async def connect(settings: Settings | None = None) -> asyncpg.Pool:
    settings = settings or get_settings()
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=5,
        server_settings={"search_path": f"{settings.db_schema},public"},
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
