# ingest-api

Сервис принимает `raw session package`, сохраняет metadata в `Postgres` и управляет artifact upload lifecycle в `MinIO/S3`.

## Реализация C2-C4

Реализованные endpoint-ы:

1. `POST /v1/raw-sessions`
2. `GET /v1/raw-sessions/{session_id}`
3. `POST /v1/raw-sessions/{session_id}/artifacts/presign`
4. `POST /v1/raw-sessions/{session_id}/artifacts/complete`
5. `POST /v1/raw-sessions/{session_id}/finalize`
6. `GET /health`

Ключевые runtime-функции:

1. запись manifest metadata в схему `ingest` (`Postgres`);
2. выдача presigned `PUT` URL для artifact upload;
3. перевод статусов `pending -> uploaded -> verified`;
4. finalize-проверки и перевод ingest в `ingested` или `failed`;
5. idempotency для create/complete/finalize через `Idempotency-Key`.
6. full-package checksum policy в `finalize`:
   - канонический `checksum_file_path` (`checksums/SHA256SUMS`);
   - валидация `SHA256SUMS` формата и покрытия артефактов;
   - сверка `package_checksum_sha256` и checksum-манифеста с ingest artifacts.

## Локальный запуск

Через compose-стек (рекомендуется):

```bash
docker compose -f infra/compose/raw-ingest-stack.yml up --build
```

Ручной запуск сервиса (из `services/ingest-api`):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # при необходимости
set -a && source .env && set +a
ingest-api-migrate
ingest-api
```

## Миграции

Файлы миграций:

1. `migrations/0001_raw_ingest_metadata.sql`
2. `migrations/0002_ingest_runtime_support.sql`
3. `migrations/0003_personalization_profiles.sql`

Применение:

```bash
ingest-api-migrate
```

## Структура

```text
services/ingest-api/
  pyproject.toml
  .env.example
  README.md
  src/
    ingest_api/
      api.py
      config.py
      db.py
      main.py
      migrate.py
      models.py
      repository.py
      service.py
      storage.py
  migrations/
  tests/
  deploy/
```

Связанные документы:

1. `contracts/http/raw-session-ingest.openapi.yaml`
2. `docs/backend/raw-ingest-c1.md`
3. `docs/backend/raw-ingest-c2.md`
4. `docs/backend/raw-ingest-c3.md`
5. `docs/backend/raw-ingest-c4.md`
