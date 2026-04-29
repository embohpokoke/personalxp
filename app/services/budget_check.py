from datetime import date, timedelta
from decimal import Decimal

import asyncpg

from app.services.telegram import send_budget_alert


def period_bounds(period: str, today: date) -> tuple[date, date]:
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1) - timedelta(days=1)
    return start, end


async def check_budget_after_transaction(
    conn: asyncpg.Connection,
    *,
    transaction_id: int,
    category_id: int | None,
    txn_type: str,
    txn_date: date,
) -> None:
    if txn_type != "expense" or category_id is None:
        return

    budgets = await conn.fetch(
        """
        SELECT b.id, b.limit_amount, b.period, b.start_date, b.end_date, b.alert_telegram, c.name AS category
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        WHERE b.category_id = $1
          AND b.alert_telegram = true
          AND b.start_date <= $2
          AND (b.end_date IS NULL OR b.end_date >= $2)
        """,
        category_id,
        txn_date,
    )

    for budget in budgets:
        start_date, end_date = period_bounds(budget["period"], txn_date)
        if start_date < budget["start_date"]:
            start_date = budget["start_date"]
        if budget["end_date"] and end_date > budget["end_date"]:
            end_date = budget["end_date"]

        spent = await conn.fetchval(
            """
            SELECT COALESCE(sum(amount_idr), 0)
            FROM transactions
            WHERE type = 'expense'
              AND category_id = $1
              AND txn_date BETWEEN $2 AND $3
            """,
            category_id,
            start_date,
            end_date,
        )
        spent = Decimal(spent or 0)
        limit_amount = Decimal(budget["limit_amount"])
        if spent >= limit_amount:
            await send_budget_alert(
                f"Budget alert: {budget['category']} spending is {spent:,.0f} IDR "
                f"against a {limit_amount:,.0f} IDR {budget['period']} limit "
                f"after transaction #{transaction_id}."
            )
