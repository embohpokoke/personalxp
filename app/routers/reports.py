from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.db import get_pool
from app.deps import actor_from_request
from app.schemas import CategoryTotal, ReportSummary
from app.services.pdf_export import monthly_report_pdf


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def period_bounds(period: Literal["weekly", "monthly"], today: date) -> tuple[date, date]:
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    return month_bounds(today.year, today.month)


def insight_text(
    *,
    period: str,
    expense_idr: Decimal,
    income_idr: Decimal,
    category_totals: list[CategoryTotal],
) -> list[str]:
    insights = []
    expense_categories = [item for item in category_totals if item.type == "expense"]
    if expense_categories:
        top = max(expense_categories, key=lambda item: item.total_idr)
        insights.append(f"Top expense category this {period}: {top.category} at IDR {top.total_idr:,.0f}.")
    if expense_idr > income_idr and income_idr > 0:
        insights.append("Expenses are higher than income for this period.")
    elif income_idr > 0:
        insights.append("Income covers expenses for this period.")
    if not insights:
        insights.append("No spending activity recorded for this period yet.")
    return insights


async def build_summary(
    conn: asyncpg.Connection,
    *,
    period: Literal["weekly", "monthly", "custom"],
    start_date: date,
    end_date: date,
) -> ReportSummary:
    totals = await conn.fetchrow(
        """
        SELECT
          COALESCE(sum(amount_idr) FILTER (WHERE type = 'income'), 0) AS income_idr,
          COALESCE(sum(amount_idr) FILTER (WHERE type = 'expense'), 0) AS expense_idr,
          COALESCE(sum(amount_idr) FILTER (WHERE type = 'transfer'), 0) AS transfer_idr,
          count(*) AS transaction_count
        FROM transactions
        WHERE txn_date BETWEEN $1 AND $2
        """,
        start_date,
        end_date,
    )
    rows = await conn.fetch(
        """
        SELECT
          t.category_id,
          COALESCE(c.name, 'Uncategorized') AS category,
          t.type,
          COALESCE(sum(t.amount_idr), 0) AS total_idr,
          count(*) AS count
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.txn_date BETWEEN $1 AND $2
        GROUP BY t.category_id, c.name, t.type
        ORDER BY total_idr DESC
        """,
        start_date,
        end_date,
    )
    category_totals = [
        CategoryTotal(
            category_id=row["category_id"],
            category=row["category"],
            type=row["type"],
            total_idr=row["total_idr"],
            count=row["count"],
        )
        for row in rows
    ]
    income_idr = Decimal(totals["income_idr"])
    expense_idr = Decimal(totals["expense_idr"])
    transfer_idr = Decimal(totals["transfer_idr"])
    return ReportSummary(
        period=period,
        start_date=start_date,
        end_date=end_date,
        income_idr=income_idr,
        expense_idr=expense_idr,
        transfer_idr=transfer_idr,
        net_idr=income_idr - expense_idr,
        transaction_count=totals["transaction_count"],
        category_totals=category_totals,
        insights=insight_text(
            period=period,
            expense_idr=expense_idr,
            income_idr=income_idr,
            category_totals=category_totals,
        ),
    )


@router.get("/summary", response_model=ReportSummary)
async def summary(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    period: Literal["weekly", "monthly", "custom"] = "monthly",
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> ReportSummary:
    await actor_from_request(request, pool)
    if period == "custom":
        if not from_date or not to_date:
            raise HTTPException(status_code=400, detail="from and to dates are required for custom period")
        start_date, end_date = from_date, to_date
    else:
        start_date, end_date = period_bounds(period, date.today())
    async with pool.acquire() as conn:
        return await build_summary(conn, period=period, start_date=start_date, end_date=end_date)


@router.get("/monthly.pdf")
async def monthly_pdf(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> Response:
    await actor_from_request(request, pool)
    start_date, end_date = month_bounds(year, month)
    async with pool.acquire() as conn:
        summary = await build_summary(conn, period="monthly", start_date=start_date, end_date=end_date)
    pdf = monthly_report_pdf(summary)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="personalxp-{year}-{month:02d}.pdf"'},
    )


@router.get("/period.pdf")
async def period_pdf(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> Response:
    await actor_from_request(request, pool)
    async with pool.acquire() as conn:
        summary = await build_summary(conn, period="custom", start_date=from_date, end_date=to_date)
    pdf = monthly_report_pdf(summary)
    filename = f"personalxp-{from_date.isoformat()}-to-{to_date.isoformat()}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
