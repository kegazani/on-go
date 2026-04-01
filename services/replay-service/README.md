# replay-service

Сервис строит `replay_manifest` для уже загруженных raw-сессий и отдает синхронизированные окна воспроизведения для replay-only проверки inference-пайплайна в non-live сценариях.

## Реализация D1-D3

Реализованные endpoint-ы:

1. `GET /v1/replay/sessions/{session_id}/manifest`
2. `POST /v1/replay/sessions/{session_id}/windows`
3. `POST /v1/replay/sessions/{session_id}/runs`
4. `GET /v1/replay/runs`
5. `GET /v1/replay/runs/{run_id}`
6. `GET /v1/replay/runs/{run_id}/events` (`text/event-stream`)
7. `GET /health`

Ключевые runtime-функции:

1. чтение метаданных сессии, сегментов и stream-связок из `Postgres` (схема `ingest`);
2. сборка `replay_manifest` с ссылками на stream sample artifacts в `MinIO/S3`;
3. загрузка `samples.csv(.gz)` из object storage и построение синхронизированного окна по `offset_ms`;
4. поддержка режимов `realtime` и `accelerated` через `replay_at_offset_ms`;
5. возврат session events в пределах replay-окна.
6. orchestration modes для replay run: `single_window` и `full_session`;
7. in-memory replay run registry со статусами `created/running/completed/failed`;
8. SSE-стриминг replay окон и итогового статуса run.

## Интеграционный e2e-тест (D2)

Для полного локального стека (`Postgres + MinIO + ingest-api + replay-service`) добавлен e2e runner:

```bash
python3 services/replay-service/tests/stack_e2e.py
```

Сценарий:

1. регистрирует fixture raw-session через ingest lifecycle;
2. загружает artifacts в MinIO через presigned URLs;
3. завершает ingest (`complete + finalize`);
4. проверяет replay manifest и replay window (`accelerated` mode).

## Streaming e2e-тест (D3)

```bash
python3 services/replay-service/tests/stack_stream_e2e.py
```

Сценарий:

1. выполняет базовый `stack_e2e` (готовит ingested session для replay);
2. создает replay run через `POST /v1/replay/sessions/{session_id}/runs`;
3. читает SSE поток `GET /v1/replay/runs/{run_id}/events`;
4. проверяет события `replay_window` и `run_completed`.

## Локальный запуск

Ручной запуск сервиса (из `services/replay-service`):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # при необходимости
set -a && source .env && set +a
replay-service
```

По умолчанию сервис стартует на `http://localhost:8090`.

## Структура

```text
services/replay-service/
  pyproject.toml
  .env.example
  README.md
  src/
    replay_service/
      api.py
      config.py
      db.py
      errors.py
      main.py
      models.py
      repository.py
      service.py
      storage.py
  tests/
  deploy/
```

Связанные артефакты шагов `D1-D3`:

1. `contracts/http/raw-session-replay.openapi.yaml`
2. `docs/backend/replay-d1.md`
3. `docs/backend/replay-d2.md`
4. `docs/backend/replay-d3.md`
5. `services/ingest-api/` (source raw ingest metadata + storage)
