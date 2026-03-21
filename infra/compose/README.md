# Local Infrastructure

Локальная инфраструктура для разработки backend-фаз.

## Стеки

### on-go-stack.yml (рекомендуется)

Полный стек для разработки и тестирования с мобильным приложением:

- `postgres` (5432)
- `minio` + `minio-init` (9000, 9001)
- `ingest-api` (8080) — точка входа для iPhone
- `replay-service` (8090)

Запуск:

```bash
./scripts/run-stack.sh
```

Или:

```bash
docker compose -f infra/compose/on-go-stack.yml up --build
```

### raw-ingest-stack.yml

Минимальный стек (ingest-only):

- `postgres`
- `minio` + `minio-init`
- `ingest-api`

```bash
docker compose -f infra/compose/raw-ingest-stack.yml up --build
```

## Подключение мобильного приложения

См. [Local Docker Setup](../../docs/setup/local-docker-setup.md).
