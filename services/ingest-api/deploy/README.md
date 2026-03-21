# Deploy

Для локального запуска шага `C2` используется:

1. `Dockerfile` — сборка контейнера `ingest-api`;
2. `infra/compose/raw-ingest-stack.yml` — локальный стек `Postgres + MinIO + ingest-api`.
