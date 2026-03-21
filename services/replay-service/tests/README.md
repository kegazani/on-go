# Tests

В шаге `D1` добавлены базовые unit-тесты для replay-логики.

Следующий инкремент для тестов:

1. интеграционные replay-тесты на локальном compose-стеке `Postgres + MinIO + ingest-api + replay-service`;
2. API-контрактные тесты against `raw-session-replay.openapi.yaml`;
3. проверка больших multi-stream сессий и профилирование latency.
