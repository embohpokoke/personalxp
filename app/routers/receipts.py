from pathlib import Path
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.db import get_pool
from app.deps import actor_from_request


router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.get("/{file_path:path}")
async def get_receipt(
    file_path: str,
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> FileResponse:
    await actor_from_request(request, pool)
    settings = get_settings()
    receipts_dir = settings.receipts_dir.resolve()
    target = (receipts_dir / file_path).resolve()

    if not target.is_relative_to(receipts_dir):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="receipt not found")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT mime_type
            FROM receipts
            WHERE file_path = $1
            """,
            file_path,
        )

    if row is None or not Path(target).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="receipt not found")

    return FileResponse(target, media_type=row["mime_type"])
