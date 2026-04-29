from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.db import get_pool
from app.deps import actor_from_request
from app.schemas import CategoryCreate, CategoryPublic


router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


def category_public(row: asyncpg.Record) -> CategoryPublic:
    return CategoryPublic(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        icon=row["icon"],
        is_custom=row["is_custom"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[CategoryPublic])
async def list_categories(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> list[CategoryPublic]:
    await actor_from_request(request, pool)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, type, icon, is_custom, created_at
            FROM categories
            ORDER BY type, name
            """
        )
    return [category_public(row) for row in rows]


@router.post("", response_model=CategoryPublic, status_code=201)
async def create_category(
    payload: CategoryCreate,
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> CategoryPublic:
    await actor_from_request(request, pool)
    category_name = payload.name.strip()
    if not category_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="category name is required",
        )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO categories (name, type, icon, is_custom)
            VALUES ($1, $2, $3, true)
            ON CONFLICT (name, type)
            DO UPDATE SET icon = COALESCE(EXCLUDED.icon, categories.icon)
            RETURNING id, name, type, icon, is_custom, created_at
            """,
            category_name,
            payload.type,
            payload.icon,
        )
    return category_public(row)
