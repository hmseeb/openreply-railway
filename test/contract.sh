#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
IMAGE=${IMAGE:-openreply-railway:contract}
COMMIT=c78b2d2f68c9764ef7a7dde51dfa5bfa99304a09

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[[ -f "$ROOT/Dockerfile" ]] || fail "Dockerfile is missing"
[[ -x "$ROOT/boot.sh" ]] || fail "boot.sh is missing or not executable"

grep -Fq "$COMMIT" "$ROOT/Dockerfile" || fail "Dockerfile does not pin upstream commit $COMMIT"
grep -Fq 'prisma migrate deploy' "$ROOT/boot.sh" || fail "boot.sh does not apply migrations"
grep -Eq 'next start.*(-H|--hostname)[ =]::' "$ROOT/boot.sh" || fail "web process is not bound to IPv6"
grep -Fq 'worker/dm-worker.ts' "$ROOT/boot.sh" || fail "worker process is missing"

grep -Eq 'install .*wget' "$ROOT/Dockerfile" || fail "runtime image lacks wget for scripts/cron.sh"

[[ "${STATIC_ONLY:-}" == 1 ]] && { echo "PASS: static checks"; exit 0; }

docker build -t "$IMAGE" "$ROOT"
docker run --rm --entrypoint sh "$IMAGE" -c 'command -v wget && test -f /app/scripts/cron.sh && test -f /app/node_modules/.bin/prisma' >/dev/null \
  || fail "image lacks wget, scripts/cron.sh, or prisma"

echo "PASS: image builds with pinned source, migrations, dual-stack web, worker and cron roles"
