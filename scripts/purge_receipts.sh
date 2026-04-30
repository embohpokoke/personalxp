#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${PERSONAL_XP_ENV_FILE:-/root/.wallet/personal-xp.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-livininbintaro-db}"
POSTGRES_DB="${POSTGRES_DB:-livininbintaro}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
DB_SCHEMA="${DB_SCHEMA:-personal_xp}"
RECEIPTS_DIR="${RECEIPTS_DIR:-/opt/personal-xp/receipts}"

if [[ ! "$DB_SCHEMA" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "invalid DB_SCHEMA: $DB_SCHEMA" >&2
  exit 1
fi

if [[ "$RECEIPTS_DIR" == "/" ]]; then
  echo "refusing to purge receipts from /" >&2
  exit 1
fi

mapfile -t expired_paths < <(
  docker exec "$POSTGRES_CONTAINER" psql \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -At \
    -c "SELECT file_path FROM ${DB_SCHEMA}.receipts WHERE expires_at < now();"
)

deleted_files=0
for relative_path in "${expired_paths[@]}"; do
  [[ -z "$relative_path" ]] && continue
  case "$relative_path" in
    /*|*..*|*$'\r'*|*$'\n'*)
      echo "skipping unsafe receipt path: $relative_path" >&2
      continue
      ;;
  esac
  if [[ -f "$RECEIPTS_DIR/$relative_path" ]]; then
    rm -f "$RECEIPTS_DIR/$relative_path"
    deleted_files=$((deleted_files + 1))
  fi
done

deleted_rows="$(
  docker exec "$POSTGRES_CONTAINER" psql \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -At \
    -c "WITH deleted AS (DELETE FROM ${DB_SCHEMA}.receipts WHERE expires_at < now() RETURNING id) SELECT count(*) FROM deleted;"
)"

echo "purged receipt files=$deleted_files rows=$deleted_rows"
