from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.db import get_pool
from app.deps import actor_from_request
from app.schemas import BudgetCreate, BudgetPublic


router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])


def budget_public(row: asyncpg.Record) -> BudgetPublic:
    return BudgetPublic(
        id=row["id"],
        category_id=row["category_id"],
        category=row["category"],
        limit_amount=row["limit_amount"],
        period=row["period"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        alert_telegram=row["alert_telegram"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[BudgetPublic])
async def list_budgets(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> list[BudgetPublic]:
    await actor_from_request(request, pool)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.*, c.name AS category
            FROM budgets b
            JOIN categories c ON c.id = b.category_id
            ORDER BY b.created_at DESC, b.id DESC
            """
        )
    return [budget_public(row) for row in rows]


@router.post("", response_model=BudgetPublic, status_code=201)
async def create_budget(
    payload: BudgetCreate,
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> BudgetPublic:
    await actor_from_request(request, pool)
    if payload.end_date is not None and payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )

    async with pool.acquire() as conn:
        category_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM categories WHERE id = $1)",
            payload.category_id,
        )
        if not category_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")

        row = await conn.fetchrow(
            """
            INSERT INTO budgets (category_id, limit_amount, period, start_date, end_date, alert_telegram)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING
              id,
              category_id,
              (SELECT name FROM categories WHERE id = budgets.category_id) AS category,
              limit_amount,
              period,
              start_date,
              end_date,
              alert_telegram,
              created_at
            """,
            payload.category_id,
            payload.limit_amount,
            payload.period,
            payload.start_date,
            payload.end_date,
            payload.alert_telegram,
        )
    return budget_public(row)
