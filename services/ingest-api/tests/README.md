# Tests

В шаге `C2` добавлен runtime-сервис и локальная инфраструктура.

Рекомендуемые следующие тесты (следующий инкремент):

1. контрактные тесты endpoint-ов against `raw-session-ingest.openapi.yaml`;
2. интеграционные тесты upload/finalize на локальном compose-стеке;
3. проверка idempotency-веток для create/complete/finalize.
