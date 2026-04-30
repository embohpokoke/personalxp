# Local Sign-Off

Phase 8 confirms that the repo is ready for read-only VPS preflight. It does not approve deployment by itself.

## Status

Date: 2026-04-30 Asia/Jakarta

Decision: ready for read-only VPS preflight.

Deployment remains blocked until the preflight results match `docs/DEPLOYMENT.md`.

## Scope Reviewed

- FastAPI backend and auth
- PostgreSQL schema and local seed path
- Vue/Tailwind PWA frontend
- receipt upload and cleanup
- budget, report, and PDF endpoints
- Hermes/OpenClaw ingestion contract
- production Nginx and systemd files
- production backup and receipt purge scripts
- deployment and agent documentation
- secret hygiene in the public repo

## Verification Run

```bash
.venv/bin/python -m py_compile app/main.py app/config.py app/db.py app/auth.py app/deps.py app/schemas.py app/routers/auth.py app/routers/categories.py app/routers/transactions.py app/routers/receipts.py app/routers/budgets.py app/routers/reports.py app/services/telegram.py app/services/budget_check.py app/services/pdf_export.py scripts/migrate_local.py scripts/check_seed.py scripts/smoke_local.py
.venv/bin/python -m pytest -q
node --check frontend/app.js
bash -n scripts/backup.sh scripts/purge_receipts.sh
make seed-check
SMOKE_PIN='<local-pin>' make smoke
git diff --check
```

Results:

- Python compile checks passed.
- Pytest passed: `12 passed`.
- Frontend JavaScript syntax check passed.
- Production shell scripts passed syntax check.
- Seed check passed on local DB.
- End-to-end smoke passed.
- Whitespace diff check passed.
- Local server was stopped after smoke.

## Sign-Off Checklist

| Item | Status |
|---|---|
| Backend API complete enough for v1 | Pass |
| Frontend usable on mobile-first PWA shell | Pass |
| PIN login works without committing PIN | Pass |
| Agent ingestion contract tested locally | Pass |
| Receipt upload, retrieval, and cleanup work locally | Pass |
| Reports and monthly PDF work locally | Pass |
| Budget dry-run flow exists | Pass |
| Deployment package exists | Pass |
| Backup and purge scripts exist | Pass |
| Deployment docs are executable by an agent | Pass |
| Public repo has no plaintext PIN | Pass |
| Public repo avoids specific personal names | Pass |
| Local working tree clean after commit/push | Pass after Phase 8 push |

## Next Allowed Step

Run only the read-only VPS preflight from `docs/DEPLOYMENT.md`.

Do not create files, install services, create schemas, reload Nginx, or write wallet secrets until preflight results are reviewed.

## Read-Only Preflight Commands

```bash
ssh vps-host
set -euo pipefail
ss -lntp | grep -E ':8004\b' || echo "8004 free"
docker ps --format '{{.Names}}\t{{.Status}}' | grep livininbintaro-db
schema_exists="$(docker exec livininbintaro-db psql -U postgres -d livininbintaro -At -c "SELECT 1 FROM pg_namespace WHERE nspname = 'personal_xp';")"
[[ "$schema_exists" == "1" ]] && echo "schema EXISTS - stop" || echo "schema absent"
dig +short xp.embohpokoke.my.id
test -e /opt/personal-xp && echo "app path EXISTS - stop" || echo "app path absent"
test -e /etc/nginx/conf.d/xp.embohpokoke.my.id.conf && echo "nginx conf EXISTS - stop" || echo "nginx conf absent"
test -e /root/.wallet/personal-xp.env && echo "wallet EXISTS - stop" || echo "wallet absent"
nginx -t
```
