# D3 - Streaming replay transport и orchestration modes

## Цель шага

Добавить потоковый replay transport, orchestration modes и run registry для управляемых replay-прогонов.

## Что реализовано

1. Новые API endpoint-ы replay:
   - `POST /v1/replay/sessions/{session_id}/runs`;
   - `GET /v1/replay/runs`;
   - `GET /v1/replay/runs/{run_id}`;
   - `GET /v1/replay/runs/{run_id}/events` (`text/event-stream`).
2. Добавлен `ReplayRunRegistry` (in-memory):
   - создание run;
   - получение/список run;
   - статусы `created`, `running`, `completed`, `failed`.
3. Добавлены orchestration modes:
   - `single_window`;
   - `full_session`.
4. Добавлен streaming transport (SSE):
   - события `replay_window`;
   - финальные события `run_completed` / `run_failed`.
5. Расширен `OpenAPI` контракт `raw-session-replay.openapi.yaml` под run/streaming API.

## Тесты и верификация

Добавлены:

1. `services/replay-service/tests/test_run_registry.py`
2. `services/replay-service/tests/test_orchestration.py`
3. `services/replay-service/tests/stack_stream_e2e.py`
4. `services/replay-service/tests/test_streaming_stack.py`

Локальная проверка в этом шаге:

```bash
python3 -m compileall -q services/replay-service/src services/replay-service/tests
docker compose -f infra/compose/on-go-stack.yml up -d --build
python3 services/replay-service/tests/stack_stream_e2e.py
```

Результат: `stack-stream-e2e` завершился успешно (`[stack-stream-e2e] OK`).

## Измененные файлы

1. `services/replay-service/src/replay_service/api.py`
2. `services/replay-service/src/replay_service/service.py`
3. `services/replay-service/src/replay_service/models.py`
4. `services/replay-service/src/replay_service/run_registry.py`
5. `contracts/http/raw-session-replay.openapi.yaml`
6. `services/replay-service/tests/test_run_registry.py`
7. `services/replay-service/tests/test_orchestration.py`
8. `services/replay-service/tests/stack_stream_e2e.py`
9. `services/replay-service/tests/test_streaming_stack.py`
10. `services/replay-service/README.md`
11. `services/replay-service/tests/README.md`
12. `docs/backend/replay-d3.md`
