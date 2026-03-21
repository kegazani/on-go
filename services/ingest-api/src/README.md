# Source

Runtime-код ingest-api находится в пакете `src/ingest_api`:

1. `api.py` — HTTP-роуты и wiring `FastAPI`.
2. `service.py` — бизнес-логика ingest lifecycle.
3. `repository.py` — SQL-доступ к `Postgres`.
4. `storage.py` — интеграция с `MinIO/S3`.
5. `migrate.py` — runner SQL-миграций.
