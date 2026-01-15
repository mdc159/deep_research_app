#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

set -a
source .env
set +a

cleanup_on_failure() {
  echo "Pipeline failed. Showing logs." >&2
  docker compose logs --no-color
}

trap cleanup_on_failure ERR

docker compose build

docker compose up -d

until docker compose exec -T supabase-db pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; do
  sleep 2
  echo "Waiting for database..."
done

until curl -fsS http://localhost:9000/minio/health/live >/dev/null 2>&1; do
  sleep 2
  echo "Waiting for MinIO..."
done

docker compose exec -T supabase-db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /migrations/0001_init.sql

job_id=$(python sandbox/seed_job.py)
python sandbox/verify.py "$job_id"
