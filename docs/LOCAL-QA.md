# Local QA

## Phase 1 Gate

- Local PostgreSQL starts.
- `db/001_init.sql` applies from scratch.
- One shared user exists.
- At least eleven default categories exist.

## Phase 2 Gate

- `GET /api/v1/healthz` returns `{"status":"ok"}`.
- `POST /api/v1/auth/login` accepts the configured PIN.
- `GET /api/v1/auth/me` works with the session cookie.
- `POST /api/v1/auth/logout` clears the session.
- Bad PIN returns `401`.
- Valid Hermes/OpenClaw agent headers pass auth.
- Invalid agent key returns `401`.

## Phase 3 Gate

- `GET /api/v1/categories` returns categories for an authenticated caller.
- `POST /api/v1/categories` creates or reuses a custom category.
- Web `POST /api/v1/transactions` creates a transaction from multipart form data.
- Receipt upload stores a file and creates a `receipts` row.
- `GET /receipts/{file}` streams a receipt only for an authenticated caller.
- `GET /api/v1/transactions` lists transactions with pagination metadata.
- `PATCH /api/v1/transactions/{id}` updates transaction fields and recalculates `amount_idr`.
- `DELETE /api/v1/transactions/{id}` deletes the row and removes linked receipt files.
- Hermes-style transaction ingestion with `X-Agent-Name: hermes` returns `201`.
- OpenClaw-style transaction ingestion with `X-Agent-Name: openclaw` returns `201`.
- Wrong agent key returns `401` and records `agent_audit.result = rejected`.

## Phase 4 Gate

- `GET /api/v1/budgets` lists configured budgets.
- `POST /api/v1/budgets` creates a category budget.
- Creating an expense over an active budget limit triggers a Telegram dry-run alert in local logs.
- `GET /api/v1/reports/summary?period=weekly` returns period totals and category totals.
- `GET /api/v1/reports/summary?period=monthly` returns period totals and insight text.
- `GET /api/v1/reports/monthly.pdf?year=&month=` returns a valid PDF.

## Phase 5 Gate

- `/` serves the PWA shell locally through FastAPI.
- PIN login works in the browser.
- Dashboard loads live monthly summary, category totals, chart, and recent transactions.
- Transactions view loads, filters, and refreshes live data.
- Add Expense view creates a multipart transaction through the UI.
- Budgets view lists and creates budgets.
- Reports view shows monthly breakdown and offers PDF download.
- Manifest and service worker are served.
- PWA icons exist at `/icons/icon-192.png` and `/icons/icon-512.png`.
- Mobile and desktop screenshots show the Stitch-inspired visual system without clipped primary controls.

## Commands

```bash
make seed-check
.venv/bin/python -m pytest -q
node --check frontend/app.js
```
