from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
import os
import sys
from typing import Any

import httpx


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8004").rstrip("/")
SMOKE_PIN = os.getenv("SMOKE_PIN")
AGENT_KEY = os.getenv("SMOKE_AGENT_KEY") or os.getenv("AGENT_KEY_HERMES") or "change-me"
TODAY = date.today().isoformat()
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?"
    b"\x00\x05\xfe\x02\xfeA\xe2&\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)


class SmokeFailure(RuntimeError):
    pass


def require_pin() -> str:
    if not SMOKE_PIN:
        raise SmokeFailure("SMOKE_PIN is required. Example: SMOKE_PIN='<local-pin>' make smoke")
    return SMOKE_PIN


def assert_status(response: httpx.Response, expected: int | set[int], label: str) -> None:
    expected_set = {expected} if isinstance(expected, int) else expected
    if response.status_code in expected_set:
        return
    body = response.text.replace("\n", " ")[:500]
    raise SmokeFailure(f"{label}: expected {sorted(expected_set)}, got {response.status_code}. Body: {body}")


def assert_json_field(payload: dict[str, Any], field: str, label: str) -> Any:
    value = payload.get(field)
    if value is None:
        raise SmokeFailure(f"{label}: missing JSON field '{field}'")
    return value


def step(name: str) -> None:
    print(f"ok - {name}")


def create_transaction(
    client: httpx.Client,
    *,
    category: str,
    description: str,
    amount: str,
    merchant: str,
    headers: dict[str, str] | None = None,
    include_receipt: bool = False,
) -> dict[str, Any]:
    data = {
        "amount": amount,
        "type": "expense",
        "txn_date": TODAY,
        "currency": "IDR",
        "exchange_rate": "1",
        "category": category,
        "description": description,
        "merchant": merchant,
        "entered_by": "primary",
        "source_extra": json.dumps({"smoke": True, "phase": 6}),
    }
    files = None
    if include_receipt:
        files = {"receipt": ("smoke.png", PNG_BYTES, "image/png")}
    response = client.post("/api/v1/transactions", data=data, files=files, headers=headers)
    assert_status(response, 201, f"create transaction: {description}")
    return response.json()


def main() -> int:
    try:
        pin = require_pin()
        with httpx.Client(base_url=BASE_URL, timeout=10.0) as web:
            response = web.get("/api/v1/healthz")
            assert_status(response, 200, "health")
            if response.json().get("status") != "ok":
                raise SmokeFailure("health: unexpected response")
            step("health endpoint")

            for path in ("/", "/manifest.json", "/sw.js", "/icons/icon-192.png"):
                response = web.get(path)
                assert_status(response, 200, f"static asset {path}")
                if not response.content:
                    raise SmokeFailure(f"static asset {path}: empty body")
            step("PWA shell and assets")

            response = web.get("/api/v1/auth/me")
            assert_status(response, 401, "unauthenticated /me")
            step("unauthenticated session rejected")

            response = web.post("/api/v1/auth/login", json={"pin": "not-the-local-pin", "entered_by": "primary"})
            assert_status(response, 401, "bad PIN")
            step("bad PIN rejected")

            response = web.post("/api/v1/auth/login", json={"pin": pin, "entered_by": "primary"})
            assert_status(response, 200, "login")
            assert_json_field(response.json(), "user", "login")
            response = web.get("/api/v1/auth/me")
            assert_status(response, 200, "authenticated /me")
            step("PIN login and session")

            category_name = "QA Smoke"
            response = web.post(
                "/api/v1/categories",
                json={"name": category_name, "type": "expense", "icon": "qa"},
            )
            assert_status(response, 201, "create smoke category")
            category = response.json()
            category_id = assert_json_field(category, "id", "create smoke category")

            response = web.get("/api/v1/categories")
            assert_status(response, 200, "list categories")
            if not any(item["id"] == category_id for item in response.json()):
                raise SmokeFailure("list categories: smoke category not returned")
            step("category create/list")

            response = web.post(
                "/api/v1/budgets",
                json={
                    "category_id": category_id,
                    "limit_amount": "1000000",
                    "period": "monthly",
                    "start_date": TODAY,
                    "end_date": None,
                    "alert_telegram": False,
                },
            )
            assert_status(response, 201, "create budget")
            response = web.get("/api/v1/budgets")
            assert_status(response, 200, "list budgets")
            if not any(item["category_id"] == category_id for item in response.json()):
                raise SmokeFailure("list budgets: smoke budget not returned")
            step("budget create/list")

            created = create_transaction(
                web,
                category=category_name,
                description="Phase 6 smoke web transaction",
                amount="12500",
                merchant="Local QA",
                include_receipt=True,
            )
            transaction = assert_json_field(created, "transaction", "create web transaction")
            transaction_id = assert_json_field(transaction, "id", "create web transaction")
            receipt = assert_json_field(transaction, "receipt", "create web transaction")
            receipt_path = assert_json_field(receipt, "file_path", "create web transaction")

            response = web.get(f"/receipts/{receipt_path}")
            assert_status(response, 200, "fetch receipt")
            if response.content != PNG_BYTES:
                raise SmokeFailure("fetch receipt: content mismatch")
            step("web transaction with receipt")

            response = web.get("/api/v1/transactions", params={"q": "Phase 6 smoke", "limit": 10})
            assert_status(response, 200, "list transactions")
            if not any(item["id"] == transaction_id for item in response.json()["items"]):
                raise SmokeFailure("list transactions: created transaction not returned")

            response = web.patch(
                f"/api/v1/transactions/{transaction_id}",
                json={"amount": "13500", "description": "Phase 6 smoke web transaction patched"},
            )
            assert_status(response, 200, "patch transaction")
            if Decimal(str(response.json()["amount_idr"])) != Decimal("13500"):
                raise SmokeFailure("patch transaction: amount_idr did not recalculate")
            step("transaction list and patch")

            response = web.get("/api/v1/reports/summary", params={"period": "weekly"})
            assert_status(response, 200, "weekly report")
            assert_json_field(response.json(), "category_totals", "weekly report")
            response = web.get("/api/v1/reports/summary", params={"period": "monthly"})
            assert_status(response, 200, "monthly report")
            assert_json_field(response.json(), "insights", "monthly report")
            response = web.get(
                "/api/v1/reports/monthly.pdf",
                params={"year": date.today().year, "month": date.today().month},
            )
            assert_status(response, 200, "monthly PDF")
            if not response.content.startswith(b"%PDF-"):
                raise SmokeFailure("monthly PDF: response is not a PDF")
            step("reports and PDF export")

            with httpx.Client(base_url=BASE_URL, timeout=10.0) as agent:
                headers = {"X-Agent-Name": "hermes", "X-Agent-Key": AGENT_KEY}
                response = agent.get("/api/v1/auth/agent-check", headers=headers)
                assert_status(response, 200, "Hermes agent check")
                hermes_created = create_transaction(
                    agent,
                    category="QA Smoke Agent",
                    description="Phase 6 smoke Hermes transaction",
                    amount="3456",
                    merchant="Hermes QA",
                    headers=headers,
                )
                hermes_id = hermes_created["transaction"]["id"]
                response = agent.post(
                    "/api/v1/transactions",
                    data={
                        "amount": "999",
                        "type": "expense",
                        "txn_date": TODAY,
                        "category": "QA Smoke Agent",
                        "description": "Phase 6 rejected agent transaction",
                    },
                    headers={"X-Agent-Name": "hermes", "X-Agent-Key": "wrong-key"},
                )
                assert_status(response, 401, "wrong agent key")
            step("Hermes ingestion and wrong key rejection")

            response = web.delete(f"/api/v1/transactions/{transaction_id}")
            assert_status(response, 204, "delete web transaction")
            response = web.get(f"/receipts/{receipt_path}")
            assert_status(response, 404, "deleted receipt lookup")
            response = web.delete(f"/api/v1/transactions/{hermes_id}")
            assert_status(response, 204, "delete Hermes transaction")
            step("cleanup of smoke transactions")

            response = web.post("/api/v1/auth/logout")
            assert_status(response, 200, "logout")
            response = web.get("/api/v1/auth/me")
            assert_status(response, 401, "post-logout /me")
            step("logout clears session")

        print("Phase 6 smoke passed")
        return 0
    except (httpx.HTTPError, SmokeFailure) as exc:
        print(f"Phase 6 smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
