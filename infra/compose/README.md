# Local Infrastructure

Локальная и серверная инфраструктура backend.

## on-go-stack.yml

Сервисы:

- `postgres` (5432)
- `minio` + `minio-init` (9000, 9001)
- `redis` (6379)
- `ingest-api` (8080)
- `replay-service` (8090)
- `inference-api` (8100)
- `live-inference-api` (8120)
- `personalization-worker` (8110)
- `replay-infer-ui` (8121)
- `signal-processing-worker` (профиль `batch`, см. ниже)

Модель: том `on-go-models`, если `ON_GO_MODEL_VOLUME` не задан или в `.env` пустой — `./scripts/run-stack.sh` подставляет bind-mount на `data/.../m7-9-runtime-bundle-export`, когда там есть `model-bundle.manifest.json`. Иначе заполнение тома: `./scripts/bootstrap-model-volume.sh` и `ON_GO_MODEL_BUNDLE_SOURCE`.

Запуск:

```bash
cp .env.example .env
./scripts/run-stack.sh
```

Перезапуск с сохранением томов: `./scripts/restart-stack.sh` (без `down -v`).

TLS-прокси Caddy (профиль `tls`): задать `ON_GO_ENABLE_TLS_PROXY=1` в окружении или `.env` и использовать второй файл compose:

```bash
docker compose --env-file .env -f infra/compose/on-go-stack.yml -f infra/compose/on-go-stack.tls.yml --profile tls up --build
```

`run-stack.sh` подключает оба файла и передаёт `--profile tls`, если `ON_GO_ENABLE_TLS_PROXY=1`.

Подробнее: [Server deploy](../../docs/deployment/server-deploy.md).

## raw-ingest-stack.yml

Минимальный стек (ingest-only): `postgres`, `minio`, `minio-init`, `ingest-api`.

## signal-processing-worker (batch)

Одноразовый прогон по сессии с хоста:

```bash
./scripts/run-signal-worker.sh <session_id>
```

Чтобы контейнер воркера крутился в фоне (`sleep infinity`) для отладки:

```bash
docker compose -f infra/compose/on-go-stack.yml --profile batch up -d signal-processing-worker
```

## Мобильное приложение

См. [Local Docker Setup](../../docs/setup/local-docker-setup.md).
