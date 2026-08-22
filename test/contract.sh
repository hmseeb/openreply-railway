#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
IMAGE=${IMAGE:-openreply-railway:contract}
COMMIT=80fa38780e2973a0299c05019bc0d0657044220c

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

docker build -t "$IMAGE" "$ROOT"

echo "PASS: image builds with pinned source, migrations, dual-stack web, and worker roles"
