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
- `services/replay-service/` — replay manifest + window-by-window replay поверх raw session artifacts.
- `services/signal-processing-worker/` — preprocessing worker для sync/clean/quality flags и формирования clean-layer артефактов.
- `services/dataset-registry/` — registry метаданных внешних датасетов и первичный импорт (`WESAD`) в unified internal schema.
- `services/modeling-baselines/` — baseline training/evaluation pipeline для шагов `G1-G3` (`watch-only`, `fusion`, comparative report, multi-variant comparison и research-grade artifacts).
- `services/inference-api/` — online inference API для activity/arousal predictions по feature vector (K2).
