# C4 - Ingest integration/contract tests with fixtures

## Цель шага

Зафиксировать проверяемый тестовый контур для ingest lifecycle на fixture-пакетах без зависимости от внешнего `Postgres/MinIO` стека.

## Что добавлено

1. Новый тестовый набор `services/ingest-api/tests/test_ingest_lifecycle_fixtures.py`.
2. In-memory test doubles для `Database`, `IngestRepository`, `S3Storage` с monkeypatch на уровень `FastAPI app`.
3. Fixture generator raw package (`manifest/*`, `streams/*`, `checksums/SHA256SUMS`) с валидными SHA256.
4. API-level lifecycle test: `create -> presign -> complete -> finalize -> get state`.
5. Contract checks against `contracts/http/raw-session-ingest.openapi.yaml`:
   - проверка `operationId`;
   - фиксация обязательных lifecycle routes.
6. Дополнительные негативные/устойчивые сценарии:
   - `Idempotency-Key` conflict при повторном `complete` с другим payload;
   - `finalize` failure при `package_checksum_sha256` mismatch.

## Проверка

Выполнено:

```bash
cd services/ingest-api
python3 -m compileall -q src tests
```

Ограничение текущего окружения:

```bash
python3 -m pytest -q tests/test_ingest_lifecycle_fixtures.py
# /Library/Developer/CommandLineTools/usr/bin/python3: No module named pytest
```

## Измененные файлы

1. `services/ingest-api/tests/test_ingest_lifecycle_fixtures.py`
2. `services/ingest-api/tests/README.md`
3. `services/ingest-api/README.md`
4. `docs/backend/raw-ingest-c4.md`
