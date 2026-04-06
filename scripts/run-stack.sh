#!/usr/bin/env bash
set -e
source "$(dirname "$0")/stack-common.sh"
if [[ -f .env ]]; then
  docker compose --env-file .env -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${STACK_PROFILES[@]}" up --build "$@"
else
  docker compose -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${STACK_PROFILES[@]}" up --build "$@"
fi
