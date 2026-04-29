from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import secrets
from typing import Annotated, Any, Literal
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

from app.auth import decode_session_token
from app.config import get_settings
from app.db import get_pool
from app.deps import Actor, get_shared_user_id
from app.schemas import (
    ReceiptPublic,
    TransactionCreateResponse,
    TransactionListResponse,
    TransactionPatch,
    TransactionPublic,
)
from app.services.budget_check import check_budget_after_transaction


router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])

ALLOWED_RECEIPT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heic",
}


def hash_payload(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def audit_agent(
    pool: asyncpg.Pool,
    agent_name: str,
    action: str,
    payload_hash: str | None,
    result: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_audit (agent_name, action, payload_hash, result)
            VALUES ($1, $2, $3, $4)
            """,
            agent_name or "unknown",
            action,
            payload_hash,
            result,
        )


async def transaction_actor(
    request: Request,
    pool: asyncpg.Pool,
    payload_hash: str | None,
) -> Actor:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        identity = decode_session_token(token, settings)
        return Actor(
            kind="web",
            user_id=identity.user_id,
            entered_by=identity.entered_by,
            source_agent="web",
        )

    agent_name = (request.headers.get("X-Agent-Name") or "").strip().lower()
    agent_key = request.headers.get("X-Agent-Key") or ""
    if not agent_name and not agent_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )

    expected_keys = {
        "hermes": settings.agent_key_hermes,
        "openclaw": settings.agent_key_openclaw,
    }
    expected_key = expected_keys.get(agent_name)
    if not expected_key or not secrets.compare_digest(
        expected_key.encode("utf-8"),
        agent_key.encode("utf-8"),
    ):
        await audit_agent(pool, agent_name, "transaction.create", payload_hash, "rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid agent credentials",
        )

    return Actor(
        kind="agent",
        user_id=await get_shared_user_id(pool),
        entered_by=None,
        source_agent=agent_name,
    )


def parse_decimal(value: str | None, field_name: str, default: Decimal | None = None) -> Decimal:
    if value is None or value == "":
        if default is not None:
            return default
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} is required")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} is invalid") from exc
    if parsed < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} must be positive")
    return parsed


def parse_txn_date(value: str | None) -> date:
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="txn_date is required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="txn_date is invalid") from exc


def parse_source_extra(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_extra must be JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_extra must be an object")
    return parsed


def normalize_type(value: str | None) -> Literal["expense", "income"]:
    if value not in ("expense", "income"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type must be expense or income")
    return value


async def category_id_for_name(
    conn: asyncpg.Connection,
    category_name: str | None,
    txn_type: Literal["expense", "income"],
) -> int | None:
    if not category_name:
        return None
    normalized_name = category_name.strip()
    if not normalized_name:
        return None
    row = await conn.fetchrow(
        """
        INSERT INTO categories (name, type, is_custom)
        VALUES ($1, $2, true)
        ON CONFLICT (name, type)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        normalized_name,
        txn_type,
    )
    return int(row["id"])


def safe_receipt_path(receipts_dir: Path, file_path: str) -> Path | None:
    root = receipts_dir.resolve()
    target = (root / file_path).resolve()
    if not target.is_relative_to(root):
        return None
    return target


def receipt_public(row: asyncpg.Record | None) -> ReceiptPublic | None:
    if row is None or row["receipt_id"] is None:
        return None
    return ReceiptPublic(
        id=row["receipt_id"],
        file_path=row["file_path"],
        mime_type=row["mime_type"],
        byte_size=row["byte_size"],
        uploaded_at=row["uploaded_at"],
        expires_at=row["expires_at"],
    )


def parse_source_extra_row(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return None


def transaction_public(row: asyncpg.Record) -> TransactionPublic:
    return TransactionPublic(
        id=row["id"],
        user_id=row["user_id"],
        entered_by=row["entered_by"],
        source_agent=row["source_agent"],
        type=row["type"],
        amount=row["amount"],
        currency=row["currency"],
        exchange_rate=row["exchange_rate"],
        amount_idr=row["amount_idr"],
        category_id=row["category_id"],
        category=row["category"],
        description=row["description"],
        merchant=row["merchant"],
        source_extra=parse_source_extra_row(row["source_extra"]),
        txn_date=row["txn_date"],
        is_recurring=row["is_recurring"],
        recurring_pattern=row["recurring_pattern"],
        created_at=row["created_at"],
        receipt=receipt_public(row),
    )


async def fetch_transaction(conn: asyncpg.Connection, transaction_id: int) -> TransactionPublic | None:
    row = await conn.fetchrow(
        """
        SELECT
          t.*,
          c.name AS category,
          r.id AS receipt_id,
          r.file_path,
          r.mime_type,
          r.byte_size,
          r.uploaded_at,
          r.expires_at
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        LEFT JOIN receipts r ON r.transaction_id = t.id
        WHERE t.id = $1
        """,
        transaction_id,
    )
    return transaction_public(row) if row else None


async def save_receipt_file(receipt: UploadFile | None) -> tuple[str, str | None, int] | None:
    if receipt is None or not receipt.filename:
        return None

    settings = get_settings()
    mime_type = receipt.content_type or "application/octet-stream"
    extension = ALLOWED_RECEIPT_TYPES.get(mime_type)
    if extension is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported receipt type")

    content = await receipt.read()
    byte_size = len(content)
    if byte_size > settings.max_receipt_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="receipt too large")

    today = date.today()
    relative_dir = Path(str(today.year)) / f"{today.month:02d}"
    target_dir = settings.receipts_dir / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    relative_path = relative_dir / f"{uuid4().hex}{extension}"
    target_path = settings.receipts_dir / relative_path
    target_path.write_bytes(content)
    return relative_path.as_posix(), mime_type, byte_size


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    category_id: int | None = None,
    q: str | None = None,
    source_agent: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TransactionListResponse:
    await transaction_actor(request, pool, None)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    where = []
    values: list[Any] = []

    def add_filter(sql: str, value: Any) -> None:
        values.append(value)
        where.append(sql.format(i=len(values)))

    if from_date:
        add_filter("t.txn_date >= ${i}", from_date)
    if to_date:
        add_filter("t.txn_date <= ${i}", to_date)
    if category_id:
        add_filter("t.category_id = ${i}", category_id)
    if source_agent:
        add_filter("t.source_agent = ${i}", source_agent)
    if q:
        add_filter("(t.description ILIKE ${i} OR t.merchant ILIKE ${i} OR c.name ILIKE ${i})", f"%{q}%")

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"""
            SELECT count(*)
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            {where_sql}
            """,
            *values,
        )
        rows = await conn.fetch(
            f"""
            SELECT
              t.*,
              c.name AS category,
              r.id AS receipt_id,
              r.file_path,
              r.mime_type,
              r.byte_size,
              r.uploaded_at,
              r.expires_at
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            LEFT JOIN receipts r ON r.transaction_id = t.id
            {where_sql}
            ORDER BY t.txn_date DESC, t.id DESC
            LIMIT ${len(values) + 1}
            OFFSET ${len(values) + 2}
            """,
            *values,
            limit,
            offset,
        )

    return TransactionListResponse(
        items=[transaction_public(row) for row in rows],
        limit=limit,
        offset=offset,
        total=int(total or 0),
    )


@router.post("", response_model=TransactionCreateResponse, status_code=201)
async def create_transaction(
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    amount: Annotated[str | None, Form()] = None,
    type: Annotated[str | None, Form()] = None,
    txn_date: Annotated[str | None, Form()] = None,
    currency: Annotated[str, Form()] = "IDR",
    exchange_rate: Annotated[str | None, Form()] = None,
    category: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    merchant: Annotated[str | None, Form()] = None,
    entered_by: Annotated[str | None, Form()] = None,
    source_extra: Annotated[str | None, Form()] = None,
    receipt: Annotated[UploadFile | None, File()] = None,
) -> TransactionCreateResponse:
    payload_for_hash = {
        "amount": amount,
        "type": type,
        "txn_date": txn_date,
        "currency": currency,
        "exchange_rate": exchange_rate,
        "category": category,
        "description": description,
        "merchant": merchant,
        "entered_by": entered_by,
        "source_extra": source_extra,
        "receipt_name": receipt.filename if receipt else None,
    }
    payload_hash = hash_payload(payload_for_hash)
    actor = await transaction_actor(request, pool, payload_hash)

    txn_type = normalize_type(type)
    amount_decimal = parse_decimal(amount, "amount")
    exchange_rate_decimal = parse_decimal(exchange_rate, "exchange_rate", Decimal("1"))
    if exchange_rate_decimal <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="exchange_rate must be positive")
    currency_code = currency.strip().upper()
    if len(currency_code) != 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="currency must be a 3-letter code")
    txn_date_value = parse_txn_date(txn_date)
    source_extra_value = parse_source_extra(source_extra)
    entered_by_value = entered_by if entered_by in ("primary", "secondary") else actor.entered_by
    amount_idr = amount_decimal * exchange_rate_decimal
    receipt_file = await save_receipt_file(receipt)

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                category_id = await category_id_for_name(conn, category, txn_type)
                row = await conn.fetchrow(
                    """
                    INSERT INTO transactions (
                      user_id, entered_by, source_agent, type, amount, currency,
                      exchange_rate, amount_idr, category_id, description, merchant,
                      source_extra, txn_date
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13)
                    RETURNING id
                    """,
                    actor.user_id,
                    entered_by_value,
                    actor.source_agent,
                    txn_type,
                    amount_decimal,
                    currency_code,
                    exchange_rate_decimal,
                    amount_idr,
                    category_id,
                    description,
                    merchant,
                    json.dumps(source_extra_value) if source_extra_value is not None else None,
                    txn_date_value,
                )
                transaction_id = int(row["id"])
                if receipt_file is not None:
                    file_path, mime_type, byte_size = receipt_file
                    await conn.execute(
                        """
                        INSERT INTO receipts (transaction_id, file_path, mime_type, byte_size)
                        VALUES ($1, $2, $3, $4)
                        """,
                        transaction_id,
                        file_path,
                        mime_type,
                        byte_size,
                    )
                if actor.kind == "agent":
                    await conn.execute(
                        """
                        INSERT INTO agent_audit (agent_name, action, payload_hash, result)
                        VALUES ($1, 'transaction.create', $2, 'ok')
                        """,
                        actor.source_agent,
                        payload_hash,
                    )
                await check_budget_after_transaction(
                    conn,
                    transaction_id=transaction_id,
                    category_id=category_id,
                    txn_type=txn_type,
                    txn_date=txn_date_value,
                )
                transaction = await fetch_transaction(conn, transaction_id)
    except Exception:
        if receipt_file is not None:
            target = get_settings().receipts_dir / receipt_file[0]
            target.unlink(missing_ok=True)
        raise

    if transaction is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="transaction was not created")
    return TransactionCreateResponse(id=transaction.id, message="transaction created", transaction=transaction)


@router.get("/{transaction_id}", response_model=TransactionPublic)
async def get_transaction(
    transaction_id: int,
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> TransactionPublic:
    await transaction_actor(request, pool, None)
    async with pool.acquire() as conn:
        transaction = await fetch_transaction(conn, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    return transaction


@router.patch("/{transaction_id}", response_model=TransactionPublic)
async def update_transaction(
    transaction_id: int,
    payload: TransactionPatch,
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> TransactionPublic:
    await transaction_actor(request, pool, None)
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow("SELECT * FROM transactions WHERE id = $1", transaction_id)
            if current is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")

            txn_type = payload.type or current["type"]
            amount_value = payload.amount if payload.amount is not None else current["amount"]
            exchange_rate_value = (
                payload.exchange_rate if payload.exchange_rate is not None else current["exchange_rate"]
            )
            amount_idr = amount_value * exchange_rate_value
            category_id = payload.category_id
            if payload.category:
                category_id = await category_id_for_name(conn, payload.category, txn_type)
            elif category_id is None:
                category_id = current["category_id"]

            await conn.execute(
                """
                UPDATE transactions
                SET entered_by = $2,
                    type = $3,
                    amount = $4,
                    currency = $5,
                    exchange_rate = $6,
                    amount_idr = $7,
                    category_id = $8,
                    description = $9,
                    merchant = $10,
                    source_extra = $11::jsonb,
                    txn_date = $12,
                    is_recurring = $13,
                    recurring_pattern = $14
                WHERE id = $1
                """,
                transaction_id,
                payload.entered_by if payload.entered_by is not None else current["entered_by"],
                txn_type,
                amount_value,
                (payload.currency or current["currency"]).upper(),
                exchange_rate_value,
                amount_idr,
                category_id,
                payload.description if payload.description is not None else current["description"],
                payload.merchant if payload.merchant is not None else current["merchant"],
                json.dumps(payload.source_extra) if payload.source_extra is not None else current["source_extra"],
                payload.txn_date if payload.txn_date is not None else current["txn_date"],
                payload.is_recurring if payload.is_recurring is not None else current["is_recurring"],
                payload.recurring_pattern if payload.recurring_pattern is not None else current["recurring_pattern"],
            )
            transaction = await fetch_transaction(conn, transaction_id)

    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    return transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    request: Request,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> None:
    await transaction_actor(request, pool, None)
    async with pool.acquire() as conn:
        receipt_paths = await conn.fetch(
            "SELECT file_path FROM receipts WHERE transaction_id = $1",
            transaction_id,
        )
        result = await conn.execute("DELETE FROM transactions WHERE id = $1", transaction_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")
    receipts_dir = get_settings().receipts_dir
    for row in receipt_paths:
        target = safe_receipt_path(receipts_dir, row["file_path"])
        if target is not None:
            target.unlink(missing_ok=True)
