# Tests

В шагах `D1-D2` добавлены unit- и интеграционные тесты для replay-контура.

Текущее покрытие:

1. Unit-тесты парсинга/валидации replay window (`test_service.py`, `test_models.py`).
2. Full-stack replay e2e runner: `python3 services/replay-service/tests/stack_e2e.py`.
3. Pytest-обертка full-stack сценария: `test_integration_stack.py`.
4. Full-stack streaming e2e runner: `python3 services/replay-service/tests/stack_stream_e2e.py`.
5. Pytest-обертка streaming-сценария: `test_streaming_stack.py`.

Следующий инкремент для тестов:

1. API-контрактные тесты against `raw-session-replay.openapi.yaml`;
2. проверка больших multi-stream сессий и профилирование latency.
