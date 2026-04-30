# VPS Preflight

This records the first VPS read-only preflight for `personal-xp`.

No files, services, schemas, wallet secrets, cron jobs, or Nginx configs were created or changed during this check.

## Run

Date: 2026-04-30 20:46 WIB

SSH alias:

```text
vps-host
```

## Results

| Check | Expected | Result | Status |
|---|---|---|---|
| Port `8004` | free | `8004 free` | Pass |
| PostgreSQL container | `livininbintaro-db` running | `livininbintaro-db Up 2 months` | Pass |
| Schema `personal_xp` | absent | `schema absent` | Pass |
| DNS `xp.embohpokoke.my.id` | VPS IP | `72.60.78.181` | Pass |
| App path `/opt/personal-xp` | absent | `app path absent` | Pass |
| Nginx config | absent | `nginx conf absent` | Pass |
| Wallet file | absent | `wallet absent` | Pass |
| Nginx syntax | valid | `nginx.conf syntax is ok` | Pass |

Exit codes:

```text
schema=0
nginx=0
```

## Decision

Read-only VPS preflight passed.

The next phase may proceed to deployment setup only after explicit approval. That phase will create production resources:

- `/opt/personal-xp`
- `/root/.wallet/personal-xp.env`
- PostgreSQL schema `personal_xp`
- `/etc/systemd/system/personal-xp.service`
- `/etc/nginx/conf.d/xp.embohpokoke.my.id.conf`
- root crontab entries for backup and receipt purge

Do not continue into write/deploy steps automatically from this document.
