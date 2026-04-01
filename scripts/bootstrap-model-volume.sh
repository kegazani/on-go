#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
SRC="${ON_GO_MODEL_BUNDLE_SOURCE:?set ON_GO_MODEL_BUNDLE_SOURCE to the host directory containing the runtime bundle}"
envfile=()
[[ -f .env ]] && envfile+=(--env-file .env)
docker compose "${envfile[@]}" -f infra/compose/on-go-stack.yml --profile populate-models run --rm --no-deps \
  -v "${SRC}:/bundle:ro" \
  models-volume-populate \
  sh -c "rm -rf /models/* 2>/dev/null; cp -a /bundle/. /models/"
