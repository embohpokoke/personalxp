from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import budgets, reports
from app.schemas import BudgetCreate, CategoryTotal, ReportSummary
from app.services import budget_check
from app.services.pdf_export import monthly_report_pdf


class FakeAcquire:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    async def __aenter__(self) -> object:
        return self.conn

    async def __aexit__(self, *args: object) -> None:
        return None


class FakePool:
    def __init__(self, conn: object) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
        }
    )


@pytest.mark.anyio
async def test_create_budget_rejects_end_date_before_start_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def actor_from_request(_request: Request, _pool: object) -> object:
        return object()

    monkeypatch.setattr(budgets, "actor_from_request", actor_from_request)

    with pytest.raises(HTTPException) as exc:
        await budgets.create_budget(
            BudgetCreate(
                category_id=1,
                limit_amount=Decimal("100000"),
                period="monthly",
                start_date=date(2026, 4, 10),
                end_date=date(2026, 4, 9),
            ),
            request(),
            FakePool(object()),  # type: ignore[arg-type]
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "end_date must be on or after start_date"


class SummaryConn:
    async def fetchrow(self, _sql: str, *args: object) -> dict[str, object]:
        assert args == (date(2026, 4, 1), date(2026, 4, 30))
        return {
            "income_idr": Decimal("5000000"),
            "expense_idr": Decimal("125000"),
            "transaction_count": 3,
        }

    async def fetch(self, _sql: str, *args: object) -> list[dict[str, object]]:
        assert args == (date(2026, 4, 1), date(2026, 4, 30))
        return [
            {
                "category_id": 1,
                "category": "Food",
                "type": "expense",
                "total_idr": Decimal("125000"),
                "count": 2,
            },
            {
                "category_id": 2,
                "category": "Salary",
                "type": "income",
                "total_idr": Decimal("5000000"),
                "count": 1,
            },
        ]


@pytest.mark.anyio
async def test_build_summary_returns_totals_category_totals_and_insights() -> None:
    summary = await reports.build_summary(
        SummaryConn(),  # type: ignore[arg-type]
        period="monthly",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
    )

    assert summary.income_idr == Decimal("5000000")
    assert summary.expense_idr == Decimal("125000")
    assert summary.net_idr == Decimal("4875000")
    assert summary.transaction_count == 3
    assert summary.category_totals[0].category == "Food"
    assert summary.insights == [
        "Top expense category this monthly: Food at IDR 125,000.",
        "Income covers expenses for this period.",
    ]


def test_monthly_report_pdf_returns_pdf_bytes() -> None:
    summary = ReportSummary(
        period="monthly",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        income_idr=Decimal("5000000"),
        expense_idr=Decimal("125000"),
        net_idr=Decimal("4875000"),
        transaction_count=3,
        category_totals=[
            CategoryTotal(
                category_id=1,
                category="Food",
                type="expense",
                total_idr=Decimal("125000"),
                count=2,
            )
        ],
        insights=["Income covers expenses for this period."],
    )

    pdf = monthly_report_pdf(summary)

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


class BudgetCheckConn:
    async def fetch(self, _sql: str, *args: object) -> list[dict[str, object]]:
        assert args == (1, date(2026, 4, 15))
        return [
            {
                "id": 1,
                "limit_amount": Decimal("100000"),
                "period": "monthly",
                "start_date": date(2026, 4, 1),
                "end_date": None,
                "alert_telegram": True,
                "category": "Food",
            }
        ]

    async def fetchval(self, _sql: str, *args: object) -> Decimal:
        assert args == (1, date(2026, 4, 1), date(2026, 4, 30))
        return Decimal("150000")


@pytest.mark.anyio
async def test_budget_check_swallow_telegram_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_alert(_message: str) -> None:
        raise RuntimeError("telegram unavailable")

    monkeypatch.setattr(budget_check, "send_budget_alert", failing_alert)

    await budget_check.check_budget_after_transaction(
        BudgetCheckConn(),  # type: ignore[arg-type]
        transaction_id=42,
        category_id=1,
        txn_type="expense",
        txn_date=date(2026, 4, 15),
    )


@pytest.mark.anyio
async def test_budget_check_skips_income_without_querying() -> None:
    class Conn:
        async def fetch(self, *_args: object) -> None:
            raise AssertionError("income transactions should not query budgets")

    await budget_check.check_budget_after_transaction(
        Conn(),  # type: ignore[arg-type]
        transaction_id=43,
        category_id=1,
        txn_type="income",
        txn_date=date(2026, 4, 15),
    )
