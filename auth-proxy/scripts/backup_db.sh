#!/bin/sh
# Backup the auth-proxy Postgres token store via pg_dump.
#
# Runs pg_dump inside the postgres container and writes a timestamped SQL dump
# to ./backups on the host. Run from the repo root (where docker-compose.yml is):
#
#     sh auth-proxy/scripts/backup_db.sh
#
# Restore with:
#
#     docker compose exec -T postgres psql -U "$PG_USER" "$PG_DB" < backups/<file>.sql
set -e

: "${PG_USER:=authproxy}"
: "${PG_DB:=authproxy}"

TS=$(date +%Y%m%d_%H%M%S)
OUT="backups/authproxy_${TS}.sql"

mkdir -p backups
docker compose exec -T postgres pg_dump -U "$PG_USER" "$PG_DB" > "$OUT"
echo "Wrote $OUT"
