# D1: Replay service и replay manifest

## Что реализовано

Шаг `D1` закрывает первый рабочий инкремент replay-контура:

1. Добавлен отдельный runtime-сервис `replay-service` (`FastAPI`).
2. Реализованы endpoint-ы:
   - `GET /v1/replay/sessions/{session_id}/manifest`;
   - `POST /v1/replay/sessions/{session_id}/windows`;
   - `GET /health`.
3. Реализована сборка `replay_manifest` на основе уже загруженных raw session metadata и artifact-связок из `Postgres` (`ingest` schema).
4. Реализовано чтение stream sample artifacts из `MinIO/S3` и формирование синхронизированного replay-окна по `offset_ms`.
5. Поддержаны режимы replay:
   - `realtime`;
   - `accelerated` (через `speed_multiplier` и расчет `replay_at_offset_ms`).
6. Добавлен базовый `OpenAPI`-контракт replay API и базовые unit-тесты replay-логики.

## Формат replay_manifest

`replay_manifest` в `D1` возвращается API-ответом и содержит:

1. идентификацию и статус сессии (`session_id`, `subject_id`, `ingest_status`);
2. границы времени (`started_at_utc`, `ended_at_utc`, `duration_ms`, `timezone`);
3. список сегментов (`segments`) в порядке `order_index`;
4. список потоков (`streams`) с привязкой к sample artifacts:
   - `stream_name`, `stream_id`, `device_id`, `sample_count`;
   - `file_ref`, `sample_object_key`, `sample_upload_status`;
   - флаг `available_for_replay` и причина недоступности, если поток еще не готов.
5. `warnings` для неполных или пока недоступных потоков.

## Новые runtime-артефакты

1. `services/replay-service/src/replay_service/` - код API/сервиса/репозитория/интеграции с object storage.
2. `services/replay-service/tests/` - базовые unit-тесты replay request/model и stream window parsing.
3. `services/replay-service/deploy/Dockerfile` - контейнер сервиса.
4. `contracts/http/raw-session-replay.openapi.yaml` - контракт replay API.

## Как запустить локально

Из `services/replay-service`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
replay-service
```

По умолчанию сервис слушает `http://localhost:8090`.

## Границы шага D1

Что покрыто:

1. Формализован `replay_manifest` и HTTP-контур replay-сервиса.
2. Поддержано синхронизированное окно воспроизведения по нескольким потокам.
3. Поддержаны режимы `realtime/accelerated` и возврат событий `session_events` внутри окна.

Что остается для следующего шага replay-фазы:

1. потоковый transport (`SSE`/`WebSocket`) для long-running live-like replay;
2. режимы orchestration (batch jobs, replay scenarios, run registry);
3. интеграционные replay-тесты на полном локальном стеке (`Postgres + MinIO + ingest-api + replay-service`).
