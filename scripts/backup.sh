#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${PERSONAL_XP_ENV_FILE:-/root/.wallet/personal-xp.env}"
BACKUP_DIR="${PERSONAL_XP_BACKUP_DIR:-/root/backups/personal-xp}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-livininbintaro-db}"
POSTGRES_DB="${POSTGRES_DB:-livininbintaro}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

DB_SCHEMA="${DB_SCHEMA:-personal_xp}"
timestamp="$(date +%F-%H%M%S)"
target="$BACKUP_DIR/personal-xp-$timestamp.sql.gz"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

docker exec "$POSTGRES_CONTAINER" pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --schema="$DB_SCHEMA" \
  --no-owner \
  --no-privileges \
  | gzip -9 > "$target"

chmod 600 "$target"
find "$BACKUP_DIR" -type f -name 'personal-xp-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete

echo "backup written: $target"
