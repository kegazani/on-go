#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
SID="${1:?usage: $0 <session_id>}"
envfile=()
[[ -f .env ]] && envfile+=(--env-file .env)
docker compose "${envfile[@]}" -f infra/compose/on-go-stack.yml --profile batch run --rm \
  signal-processing-worker \
  signal-processing-worker --session-id "$SID"
