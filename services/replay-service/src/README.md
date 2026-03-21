# Source

Runtime-код replay-service находится в пакете `src/replay_service`:

1. `api.py` - HTTP-роуты и wiring `FastAPI`.
2. `service.py` - сборка replay manifest и формирование replay-окон.
3. `repository.py` - SQL-доступ к `Postgres` (`ingest` schema).
4. `storage.py` - чтение stream artifacts из `MinIO/S3`.
