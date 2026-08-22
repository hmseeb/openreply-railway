#!/bin/sh
set -eu

role=${1:-web}
attempt=1
until ./node_modules/.bin/prisma migrate deploy; do
  if [ "$attempt" -ge 60 ]; then
    echo "Database migrations did not succeed after 60 attempts" >&2
    exit 1
  fi
  echo "Database is not ready, retrying migration in 2 seconds ($attempt/60)"
  attempt=$((attempt + 1))
  sleep 2
done

case "$role" in
  web)
    exec ./node_modules/.bin/next start -H :: -p "${PORT:-3000}"
    ;;
  worker)
    exec ./node_modules/.bin/tsx worker/dm-worker.ts
    ;;
  *)
    echo "Unknown role: $role (expected web or worker)" >&2
    exit 64
    ;;
esac
