# personalxp

Personal expense tracker using AI agents, OpenClaw and Hermes, as receipt capture.

The app is a mobile-first installable PWA. Receipt images can be sent to OpenClaw or Hermes, where the agent extracts transaction data and posts it to the backend API.

## Stack

- Backend: FastAPI
- Database: PostgreSQL
- Frontend: Vue 3 CDN and Tailwind CDN
- Auth: shared PIN, stored only as a hash
- Agent ingestion: Hermes and OpenClaw API keys

## Local Setup

Create the virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip wheel
.venv/bin/pip install -r requirements.txt
```

Start local Postgres:

```bash
make db-up
```

If Docker is not installed but Homebrew Postgres is running, create a local database instead:

```bash
make db-local-create
```

Apply the schema with a runtime PIN:

```bash
INIT_PIN='<your-pin>' make migrate
```

Check seed data:

```bash
make seed-check
```

Run the local API:

```bash
make dev
```

Health check:

```bash
curl http://127.0.0.1:8004/api/v1/healthz
```

Run the local end-to-end smoke test while the app is running:

```bash
SMOKE_PIN='<your-pin>' make smoke
```

## Security Notes

- The PIN is never committed.
- The database stores only `users.pin_hash`.
- `.env`, receipt uploads, and backup dumps are ignored by git.
- Agent keys belong in local environment files or the production wallet, never source code.

## Production

Production deployment is documented in the Obsidian project docs and should only happen after local sign-off.
