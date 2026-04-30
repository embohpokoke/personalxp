# Agent API

Hermes and OpenClaw send normalized expense or income data to the same endpoint.

## Endpoint

Production:

```text
POST https://xp.embohpokoke.my.id/api/v1/transactions
```

Local development:

```text
POST http://127.0.0.1:8004/api/v1/transactions
```

## Authentication

Each request must include one agent name and its matching key:

```http
X-Agent-Name: hermes
X-Agent-Key: <HERMES_KEY>
```

or:

```http
X-Agent-Name: openclaw
X-Agent-Key: <OPENCLAW_KEY>
```

Keys are configured during deployment in:

```text
/root/.wallet/personal-xp.env
```

Do not share keys between agents. Do not put keys in source code.

## Request Format

Use `multipart/form-data`.

| Field | Required | Example | Notes |
|---|---:|---|---|
| `amount` | yes | `45000` | Original transaction amount |
| `type` | yes | `expense` | Must be `expense` or `income` |
| `txn_date` | yes | `2026-04-28` | ISO date |
| `currency` | no | `IDR` | Default `IDR` |
| `exchange_rate` | no | `1` | Default `1` |
| `category` | no | `Food` | Auto-created if unknown |
| `description` | no | `Lunch` | Human-readable detail |
| `merchant` | no | `Local Cafe` | Merchant/store name |
| `entered_by` | no | `primary` | `primary`, `secondary`, or blank |
| `source_extra` | no | JSON string | Agent debug/context metadata |
| `receipt` | no | file | jpeg, png, webp, or heic; max 10 MB |

Backend behavior:

- `amount_idr = amount * exchange_rate`
- If `category` does not exist, backend creates it as a custom category.
- `source_agent` is taken from `X-Agent-Name`.
- Receipt files expire after 30 days.
- Every accepted and rejected agent request is written to `agent_audit`.

## Hermes Example

```bash
curl -X POST https://xp.embohpokoke.my.id/api/v1/transactions \
  -H "X-Agent-Name: hermes" \
  -H "X-Agent-Key: $HERMES_KEY" \
  -F amount=45000 \
  -F type=expense \
  -F category=Food \
  -F merchant="Local Cafe" \
  -F txn_date=2026-04-28 \
  -F entered_by=primary \
  -F receipt=@./receipt.jpg
```

## OpenClaw Example

```bash
curl -X POST https://xp.embohpokoke.my.id/api/v1/transactions \
  -H "X-Agent-Name: openclaw" \
  -H "X-Agent-Key: $OPENCLAW_KEY" \
  -F amount=125000 \
  -F type=expense \
  -F category=Groceries \
  -F merchant="Local Market" \
  -F txn_date=2026-04-28 \
  -F entered_by=secondary \
  -F source_extra='{"ocr_confidence":0.91,"source":"telegram"}' \
  -F receipt=@./receipt.png
```

## Success Response

Expected status:

```text
201 Created
```

Expected JSON shape:

```json
{
  "id": 123,
  "message": "transaction created",
  "transaction": {
    "id": 123,
    "amount": "45000.00",
    "currency": "IDR",
    "amount_idr": "45000.00",
    "type": "expense",
    "category": "Food",
    "merchant": "Local Cafe",
    "txn_date": "2026-04-28",
    "entered_by": "primary",
    "source_agent": "hermes"
  }
}
```

## Error Responses

| Status | Meaning | Agent Action |
|---:|---|---|
| `400` | Invalid amount, type, date, or malformed form | Fix payload and retry |
| `401` | Missing/bad agent key | Stop and rotate/check key |
| `413` | Receipt too large | Compress or omit receipt |
| `415` | Unsupported receipt type | Convert to jpg/png/webp/heic |
| `422` | Valid form but semantically invalid value | Fix extracted data |
| `500` | Server error | Retry later and notify the deployment owner |

## Retry Rules

- Retry only for `500`, timeout, or network errors.
- Do not retry `400`, `401`, `413`, `415`, or `422` without changing the payload/config.
- For v1, avoid repeated automatic retries that could duplicate transactions.

## Data Extraction Rules

When reading a receipt:

- Prefer final total paid, not subtotal.
- Prefer transaction date printed on receipt.
- Use `IDR` if the receipt is Indonesian and currency is not explicit.
- Use category guesses conservatively.
- If unsure about category, use `Other`.
- If payer is known from context, set `entered_by` to `primary` or `secondary`.
- If payer is unknown, leave `entered_by` blank.

## Key Rotation

If a key leaks or fails:

1. Update `/root/.wallet/personal-xp.env`.
2. Restart the app:

```bash
systemctl restart personal-xp
```

3. Update the agent secret store.
4. Test with a small transaction.
