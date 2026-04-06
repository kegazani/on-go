#!/usr/bin/env bash
set -e
source "$(dirname "$0")/stack-common.sh"
printf '%s\n' "on-go restart: compose down (тома не трогаем, без -v)"
if [[ -f .env ]]; then
  docker compose --env-file .env -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${STACK_PROFILES[@]}" down
  printf '%s\n' "on-go restart: compose up -d --build"
  docker compose --env-file .env -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${STACK_PROFILES[@]}" up -d --build "$@"
else
  docker compose -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${STACK_PROFILES[@]}" down
  printf '%s\n' "on-go restart: compose up -d --build (без .env)"
  docker compose -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml "${STACK_PROFILES[@]}" up -d --build "$@"
fi
printf '%s\n' "on-go restart: готово. Проверка: curl -s http://localhost:8080/health"
