from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import categories, transactions
from app.schemas import CategoryCreate


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


class CategoryConn:
    def __init__(self) -> None:
        self.args: tuple[object, ...] | None = None

    async def fetchrow(self, _sql: str, *args: object) -> dict[str, object]:
        self.args = args
        return {
            "id": 1,
            "name": args[0],
            "type": args[1],
            "icon": args[2],
            "is_custom": True,
            "created_at": datetime.now(),
        }


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
async def test_create_category_rejects_whitespace_name(monkeypatch: pytest.MonkeyPatch) -> None:
    async def actor_from_request(_request: Request, _pool: object) -> object:
        return object()

    monkeypatch.setattr(categories, "actor_from_request", actor_from_request)

    with pytest.raises(HTTPException) as exc:
        await categories.create_category(
            CategoryCreate(name="   ", type="expense"),
            request(),
            FakePool(CategoryConn()),  # type: ignore[arg-type]
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "category name is required"


@pytest.mark.anyio
async def test_create_category_strips_name_before_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    async def actor_from_request(_request: Request, _pool: object) -> object:
        return object()

    monkeypatch.setattr(categories, "actor_from_request", actor_from_request)
    conn = CategoryConn()

    created = await categories.create_category(
        CategoryCreate(name="  Coffee  ", type="expense", icon="C"),
        request(),
        FakePool(conn),  # type: ignore[arg-type]
    )

    assert conn.args == ("Coffee", "expense", "C")
    assert created.name == "Coffee"


@pytest.mark.anyio
async def test_transaction_category_ingestion_ignores_whitespace_name() -> None:
    assert await transactions.category_id_for_name(object(), "   ", "expense") is None  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_delete_transaction_does_not_unlink_receipt_paths_outside_root(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipts_dir = tmp_path / "receipts"
    receipts_dir.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("keep me")

    class DeleteConn:
        async def fetch(self, _sql: str, _transaction_id: int) -> list[dict[str, str]]:
            return [{"file_path": "../outside.txt"}]

        async def execute(self, _sql: str, _transaction_id: int) -> str:
            return "DELETE 1"

    async def transaction_actor(_request: Request, _pool: object, _payload_hash: object) -> object:
        return object()

    monkeypatch.setattr(transactions, "transaction_actor", transaction_actor)
    monkeypatch.setattr(transactions, "get_settings", lambda: SimpleNamespace(receipts_dir=receipts_dir))

    await transactions.delete_transaction(
        123,
        request(),
        FakePool(DeleteConn()),  # type: ignore[arg-type]
    )

    assert outside_file.exists()
