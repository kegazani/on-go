#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
docker compose -f infra/compose/on-go-stack.yml up --build "$@"
