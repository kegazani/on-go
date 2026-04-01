# D2 - Replay integration tests на полном локальном стеке

## Цель шага

Проверить replay-контур end-to-end на полном локальном стеке `Postgres + MinIO + ingest-api + replay-service`.

## Что добавлено

1. Full-stack e2e runner: `services/replay-service/tests/stack_e2e.py`.
2. Pytest-обертка сценария: `services/replay-service/tests/test_integration_stack.py`.
3. Обновлена тестовая документация replay-сервиса (`services/replay-service/tests/README.md`).

## Покрываемый e2e сценарий

1. Проверка health endpoint-ов `ingest-api` и `replay-service`.
2. Создание fixture raw session через `POST /v1/raw-sessions`.
3. Upload всех artifacts по presigned `PUT` URL.
4. Подтверждение upload (`/artifacts/complete`) и finalize (`/finalize`).
5. Проверка `GET /v1/replay/sessions/{session_id}/manifest`:
   - stream присутствует;
   - `available_for_replay=true`.
6. Проверка `POST /v1/replay/sessions/{session_id}/windows` в `accelerated` mode:
   - корректные `offset_ms` и `replay_at_offset_ms`;
   - корректные sample values (`hr_bpm`);
   - ожидаемый `sample_count`.

## Как запускать

1. Поднять полный стек:

```bash
docker compose -f infra/compose/on-go-stack.yml up -d --build
```

2. Запустить e2e runner:

```bash
python3 services/replay-service/tests/stack_e2e.py
```

3. (Опционально) через pytest:

```bash
cd services/replay-service
python3 -m pytest -q tests/test_integration_stack.py
```

## Фактическая проверка в этом шаге

Выполнено:

```bash
docker compose -f infra/compose/on-go-stack.yml up -d --build
python3 services/replay-service/tests/stack_e2e.py
```

Результат:

- `stack-e2e` завершился успешно;
- fixture session успешно прошла ingest lifecycle и replay-window проверки.

## Измененные файлы

1. `services/replay-service/tests/stack_e2e.py`
2. `services/replay-service/tests/test_integration_stack.py`
3. `services/replay-service/tests/README.md`
4. `services/replay-service/README.md`
5. `docs/backend/replay-d2.md`
