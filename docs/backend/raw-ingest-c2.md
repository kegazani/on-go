# C2: Raw storage в Postgres + MinIO/S3

## Что реализовано

Шаг `C2` закрывает runtime-часть ingest-контура:

1. Поднят рабочий `FastAPI`-сервис `ingest-api`.
2. Реализованы endpoint-ы lifecycle:
   - `POST /v1/raw-sessions`
   - `GET /v1/raw-sessions/{session_id}`
   - `POST /v1/raw-sessions/{session_id}/artifacts/presign`
   - `POST /v1/raw-sessions/{session_id}/artifacts/complete`
   - `POST /v1/raw-sessions/{session_id}/finalize`
3. Добавлена запись manifest-метаданных в `Postgres` и lifecycle artifact-статусов.
4. Добавлена интеграция с `MinIO/S3`:
   - выдача presigned `PUT` URL;
   - проверка наличия и размера загруженных объектов через `HEAD`;
   - проверка checksum для checksum-artifact на finalize.
5. Добавлена idempotency-поддержка для операций:
   - create ingest;
   - complete batch;
   - finalize.
6. Добавлен локальный compose-стек (`Postgres + MinIO + ingest-api`) и Dockerfile сервиса.

## Новые runtime-артефакты

1. `services/ingest-api/src/ingest_api/` — код API/сервиса/репозитория/миграций runner.
2. `services/ingest-api/migrations/0002_ingest_runtime_support.sql` — idempotency table.
3. `services/ingest-api/deploy/Dockerfile` — контейнер сервиса.
4. `infra/compose/raw-ingest-stack.yml` — локальный стенд.

## Как поднять локально

Из корня `on-go`:

```bash
docker compose -f infra/compose/raw-ingest-stack.yml up --build
```

Полезные URL:

1. API: `http://localhost:8080`
2. Health: `http://localhost:8080/health`
3. MinIO API: `http://localhost:9000`
4. MinIO Console: `http://localhost:9001`

## Границы шага C2

Что покрыто:

1. Runtime ingest lifecycle c persistence в `Postgres`.
2. Upload targets и object checks в `MinIO/S3`.
3. Базовый finalize flow до `ingested/failed`.

Что останется для следующих шагов:

1. Расширенная policy-проверка полного package checksum.
2. Интеграционные и контрактные тесты с генерацией test fixtures.
3. Переход к `D1` (replay-service), использующий сохраненные raw sessions.
