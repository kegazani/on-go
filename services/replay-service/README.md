# replay-service

Сервис строит `replay_manifest` для уже загруженных raw-сессий и отдает синхронизированные окна воспроизведения для отладки и симуляции inference-пайплайна.

## Реализация D1

Реализованные endpoint-ы:

1. `GET /v1/replay/sessions/{session_id}/manifest`
2. `POST /v1/replay/sessions/{session_id}/windows`
3. `GET /health`

Ключевые runtime-функции:

1. чтение метаданных сессии, сегментов и stream-связок из `Postgres` (схема `ingest`);
2. сборка `replay_manifest` с ссылками на stream sample artifacts в `MinIO/S3`;
3. загрузка `samples.csv(.gz)` из object storage и построение синхронизированного окна по `offset_ms`;
4. поддержка режимов `realtime` и `accelerated` через `replay_at_offset_ms`;
5. возврат session events в пределах replay-окна.

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

Связанные артефакты шага `D1`:

1. `contracts/http/raw-session-replay.openapi.yaml`
2. `docs/backend/replay-d1.md`
3. `services/ingest-api/` (source raw ingest metadata + storage)
