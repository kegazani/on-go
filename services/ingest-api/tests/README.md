# Tests

В шаге `C4` добавлены интеграционные/контрактные тесты ingest lifecycle с raw package fixtures.

Текущее покрытие:

1. API-level lifecycle test: `create -> presign -> complete -> finalize -> state` с fixture-пакетом.
2. Contract route/operation checks against `contracts/http/raw-session-ingest.openapi.yaml`.
3. Idempotency conflict test для `complete`.
4. Negative finalize test для `package_checksum_sha256` mismatch.
