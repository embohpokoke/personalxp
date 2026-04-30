# Deployment

This is the production package guide for `personal-xp`.

Do not deploy before local sign-off is complete. Phase 6 local smoke must pass before any VPS changes.

## Production Target

| Item | Value |
|---|---|
| Domain | `xp.embohpokoke.my.id` |
| App path | `/opt/personal-xp` |
| Service | `personal-xp` |
| App bind | `127.0.0.1:8004` |
| Nginx config | `/etc/nginx/conf.d/xp.embohpokoke.my.id.conf` |
| Wallet | `/root/.wallet/personal-xp.env` |
| Receipts | `/opt/personal-xp/receipts` |
| Backups | `/root/backups/personal-xp` |
| Database schema | `personal_xp` |

## Files In This Repo

| File | Purpose |
|---|---|
| `nginx/xp.embohpokoke.my.id.bootstrap.conf` | HTTP-only first-run config for certbot |
| `nginx/xp.embohpokoke.my.id.conf` | Final HTTPS reverse proxy and static PWA config |
| `systemd/personal-xp.service` | systemd service unit |
| `scripts/backup.sh` | Daily schema backup |
| `scripts/purge_receipts.sh` | Daily expired receipt cleanup |
| `.env.example` | Environment variable template |
| `docs/AGENT-API.md` | Hermes/OpenClaw integration contract |

## Read-Only VPS Preflight

SSH into the VPS and run these checks before changing anything:

```bash
ssh vps-host
```

```bash
ss -lntp | grep -E ':8004\b' || echo "8004 free"
docker ps --format '{{.Names}}\t{{.Status}}' | grep livininbintaro-db
docker exec livininbintaro-db psql -U postgres -d livininbintaro -c "\dn" | grep -E 'personal_xp' && echo "schema EXISTS - stop" || echo "schema absent"
dig +short xp.embohpokoke.my.id
test -e /opt/personal-xp && echo "app path EXISTS - stop" || echo "app path absent"
test -e /etc/nginx/conf.d/xp.embohpokoke.my.id.conf && echo "nginx conf EXISTS - stop" || echo "nginx conf absent"
test -e /root/.wallet/personal-xp.env && echo "wallet EXISTS - stop" || echo "wallet absent"
nginx -t
```

Expected:

- `8004 free`
- `livininbintaro-db` running
- schema `personal_xp` absent
- `dig +short xp.embohpokoke.my.id` returns the VPS IP
- `/opt/personal-xp` absent
- active Nginx config absent
- wallet absent
- `nginx -t` passes

Stop and report if any expectation fails.

## Wallet

Create the production wallet on the VPS:

```bash
mkdir -p /root/.wallet
chmod 700 /root/.wallet
vi /root/.wallet/personal-xp.env
chmod 600 /root/.wallet/personal-xp.env
```

Template:

```bash
DATABASE_URL=postgresql://postgres:<shared-postgres-password>@127.0.0.1:5432/livininbintaro
DB_SCHEMA=personal_xp

JWT_SECRET=<openssl-rand-hex-48>
JWT_TTL_HOURS=720
SESSION_COOKIE_NAME=xp_session

AGENT_KEY_HERMES=<openssl-rand-hex-32>
AGENT_KEY_OPENCLAW=<openssl-rand-hex-32>

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID_PRIMARY=
TELEGRAM_CHAT_ID_SECONDARY=
TELEGRAM_DRY_RUN=true

RECEIPTS_DIR=/opt/personal-xp/receipts
MAX_RECEIPT_BYTES=10485760

ENV=production
LOG_LEVEL=info
```

Generate secret values on the VPS:

```bash
openssl rand -hex 48
openssl rand -hex 32
```

Do not put PINs, hashes, database passwords, Telegram tokens, or agent keys in git.

## Clone And Python Environment

```bash
git clone https://github.com/embohpokoke/personalxp /opt/personal-xp
cd /opt/personal-xp
python3.11 -m venv .venv
.venv/bin/pip install -U pip wheel
.venv/bin/pip install -r requirements.txt
mkdir -p receipts
chmod 700 receipts
mkdir -p /root/backups/personal-xp
chmod 700 /root/backups/personal-xp
```

If Python 3.11 is not available, use the newest Python 3 version installed on the VPS and verify the app starts.

## Database

Set the initial PIN only at deploy time. Generate the hash on the VPS:

```bash
cd /opt/personal-xp
.venv/bin/python - <<'PY'
from getpass import getpass
from app.auth import hash_pin
print(hash_pin(getpass("Initial PIN: ")))
PY
```

Apply the schema with only the hash inserted:

```bash
PIN_HASH='<bcrypt-hash-from-command-above>'
sed "s|__PIN_HASH_PLACEHOLDER__|$PIN_HASH|g" /opt/personal-xp/db/001_init.sql > /tmp/personal-xp-001_init.sql
docker cp /tmp/personal-xp-001_init.sql livininbintaro-db:/tmp/personal-xp-001_init.sql
docker exec livininbintaro-db psql -U postgres -d livininbintaro -f /tmp/personal-xp-001_init.sql
```

Verify:

```bash
docker exec livininbintaro-db psql -U postgres -d livininbintaro -c "SELECT count(*) AS users FROM personal_xp.users;"
docker exec livininbintaro-db psql -U postgres -d livininbintaro -c "SELECT count(*) AS categories FROM personal_xp.categories;"
```

Expected:

- `users = 1`
- `categories >= 11`

## Systemd

```bash
cp /opt/personal-xp/systemd/personal-xp.service /etc/systemd/system/personal-xp.service
systemctl daemon-reload
systemctl enable --now personal-xp
systemctl status personal-xp --no-pager
curl -sf http://127.0.0.1:8004/api/v1/healthz
```

Expected health response:

```json
{"status":"ok"}
```

## Nginx And SSL

Use the bootstrap config only if the TLS certificate does not exist yet:

```bash
mkdir -p /var/www/certbot
cp /opt/personal-xp/nginx/xp.embohpokoke.my.id.bootstrap.conf /etc/nginx/conf.d/xp.embohpokoke.my.id.conf
nginx -t
systemctl reload nginx
certbot certonly --webroot -w /var/www/certbot -d xp.embohpokoke.my.id --agree-tos --no-eff-email --non-interactive --email <admin-email>
```

After the certificate exists, install the final HTTPS config:

```bash
cp /opt/personal-xp/nginx/xp.embohpokoke.my.id.conf /etc/nginx/conf.d/xp.embohpokoke.my.id.conf
nginx -t
systemctl reload nginx
curl -sfI https://xp.embohpokoke.my.id/
curl -sf https://xp.embohpokoke.my.id/api/v1/healthz
```

## Cron

```bash
chmod +x /opt/personal-xp/scripts/backup.sh /opt/personal-xp/scripts/purge_receipts.sh
( crontab -l 2>/dev/null | grep -v personal-xp; \
  echo "15 2 * * *  /opt/personal-xp/scripts/backup.sh         >> /var/log/personal-xp-backup.log 2>&1"; \
  echo "30 3 * * *  /opt/personal-xp/scripts/purge_receipts.sh >> /var/log/personal-xp-purge.log 2>&1" \
) | crontab -
crontab -l | grep personal-xp
```

Manual backup verification:

```bash
/opt/personal-xp/scripts/backup.sh
ls -la /root/backups/personal-xp/
```

## Production Smoke

Minimum checks:

```bash
curl -sf https://xp.embohpokoke.my.id/api/v1/healthz
```

Browser checks:

- Open `https://xp.embohpokoke.my.id`
- Login with PIN
- Add manual expense
- Confirm transaction appears
- Download monthly PDF

Agent checks:

- Hermes-style POST with valid key returns `201`
- OpenClaw-style POST with valid key returns `201`
- Wrong key returns `401`
- `agent_audit` records accepted and rejected attempts

Backup check:

- `scripts/backup.sh` creates a `.sql.gz` file
- `scripts/purge_receipts.sh` runs without unsafe path deletion

## Rollback

Rollback deletes app files and the app schema. Use only with explicit approval.

```bash
systemctl disable --now personal-xp
rm -f /etc/systemd/system/personal-xp.service
systemctl daemon-reload
rm -f /etc/nginx/conf.d/xp.embohpokoke.my.id.conf
nginx -t && systemctl reload nginx
docker exec livininbintaro-db psql -U postgres -d livininbintaro -c "DROP SCHEMA personal_xp CASCADE;"
rm -rf /opt/personal-xp /root/.wallet/personal-xp.env /root/backups/personal-xp
crontab -l | grep -v personal-xp | crontab -
```
