# Production Deployment

This records the first production deployment of `personal-xp`.

## Run

Date: 2026-04-30 20:58 WIB

Production URL:

```text
https://xp.embohpokoke.my.id
```

Deployed git revision:

```text
8a9fab9
```

## Created Resources

| Resource | Status |
|---|---|
| `/opt/personal-xp` | Created from GitHub repo |
| `/root/.wallet/personal-xp.env` | Created with production-only secrets |
| PostgreSQL schema `personal_xp` | Created in `livininbintaro-db` |
| `/etc/systemd/system/personal-xp.service` | Installed and enabled |
| `/etc/nginx/conf.d/xp.embohpokoke.my.id.conf` | Installed |
| Let's Encrypt certificate | Issued |
| Backup cron | Installed |
| Receipt purge cron | Installed |

## Deployment Notes

- Plaintext PIN was not written to repo files.
- Production wallet values were not printed into this document.
- `users.pin_hash` stores only the hashed PIN.
- The app connects to schema `personal_xp` through an explicit connection search path.
- The DB user used by the app was granted scoped privileges on schema `personal_xp`.
- Nginx was updated to the modern `http2 on;` directive.
- Production smoke transactions were deleted after smoke.
- Production smoke categories and budgets were removed after smoke cleanup.

## Production Smoke Results

| Check | Result |
|---|---|
| Local service health | Pass |
| HTTPS health | Pass |
| PIN login | Pass |
| Manual transaction with receipt | Pass |
| Receipt retrieval | Pass |
| Monthly report summary | Pass |
| Monthly PDF export | Pass |
| Hermes ingestion | Pass |
| OpenClaw ingestion | Pass |
| Wrong agent key rejection | Pass |
| `agent_audit` rejected row | Pass |
| Backup script | Pass |
| Receipt purge script | Pass |

Smoke output:

```text
health=ok
login=ok
manual_transaction_receipt=ok
reports_pdf=ok
hermes=ok
openclaw=ok
wrong_key=401
backup=ok
purge=ok
rejected_audit_count=1
```

## Final Verification

| Check | Result |
|---|---|
| `systemctl is-active personal-xp` | `active` |
| `curl http://127.0.0.1:8004/api/v1/healthz` | `{"status":"ok"}` |
| `curl https://xp.embohpokoke.my.id/api/v1/healthz` | `{"status":"ok"}` |
| `nginx -t` | successful |
| Certificate expiry | 2026-07-29 |
| Deployed git revision | `8a9fab9` |
| Production seed counts after cleanup | `users=1`, `categories=11`, `transactions=0` |

Cron entries:

```cron
15 2 * * *  /opt/personal-xp/scripts/backup.sh         >> /var/log/personal-xp-backup.log 2>&1
30 3 * * *  /opt/personal-xp/scripts/purge_receipts.sh >> /var/log/personal-xp-purge.log 2>&1
```

## Follow-Up

- Share Hermes and OpenClaw keys through each agent's secret store, not through git.
- Verify the web UI on a real mobile browser.
- Optionally configure Telegram live alerts by updating `/root/.wallet/personal-xp.env` and restarting `personal-xp`.
