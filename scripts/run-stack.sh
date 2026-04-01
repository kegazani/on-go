#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
profiles=()
[[ "${ON_GO_ENABLE_TLS_PROXY:-}" == "1" ]] && profiles+=(--profile tls)
if [[ -f .env ]]; then
  docker compose --env-file .env -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${profiles[@]}" up --build "$@"
else
  docker compose -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${profiles[@]}" up --build "$@"
fi
