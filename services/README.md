# Services

Здесь находятся отдельные backend-сервисы.

Правило размещения:

```text
services/
  service-name/
    README.md
    src/            # код сервиса
    migrations/     # изменения схемы данных
    deploy/         # deployment-манифесты сервиса
    tests/          # интеграционные и контрактные тесты
```

Не стоит создавать отдельный сервис под слишком мелкую техническую задачу.
Граница сервиса должна совпадать с отдельной бизнес-ответственностью.

Первый сервис в backend-фазе:

- `services/ingest-api/` — runtime ingest lifecycle: API, Postgres metadata, MinIO/S3 artifact upload.
- `services/replay-service/` — replay manifest + window-by-window simulation поверх raw session artifacts.
- `services/signal-processing-worker/` — preprocessing worker для sync/clean/quality flags и формирования clean-layer артефактов.
