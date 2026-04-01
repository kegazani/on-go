# Contracts

Источник истины для API и событий. Swift-клиент и сервисы опираются на артефакты из этого каталога.

## Индекс контрактов (K1)

### HTTP (OpenAPI)

| Контракт | Сервис | Файл | Статус |
| --- | --- | --- | --- |
| Raw Session Ingest | ingest-api | `http/raw-session-ingest.openapi.yaml` | Активен |
| Raw Session Replay | replay-service | `http/raw-session-replay.openapi.yaml` | Активен |
| Inference API | inference-api | `http/inference-api.openapi.yaml` | K2 |
| Personalization Worker | personalization-worker | `http/personalization-worker.openapi.yaml` | K4 |
| Live Inference API | live-inference-api | `http/live-inference-api.openapi.yaml` | Live streaming |

### Schema (JSON)

| Схема | Назначение | Файл |
| --- | --- | --- |
| User Profile | Персонализация, calibration | `personalization/user-profile.schema.json` |
| Feature Contract | Входные признаки для inference | `personalization/personalization-feature-contract.schema.json` |
| Valence Canary Dashboard Snapshot | Scheduler/dashboard мониторинг scoped mode | `operations/valence-canary-dashboard.schema.json` |
| Derived State Semantics | Canonical semantic-layer output (`activity/arousal/valence -> derived_state`) | `operations/derived-state-semantics.schema.json` |
| Inference Bundle Manifest | Manifest-driven runtime bundle для per-track model/feature loading | `operations/inference-bundle-manifest.schema.json` |

Примеры semantic payloads:

- `operations/examples/inference-semantic-response.example.json`
- `operations/examples/live-inference-semantic-message.example.json`

### Events

Планируется в K2: `session.ingested`, `session.processed`, `model.promoted`.

## Версионирование

- HTTP: версия в path (`/v1/`) и заголовке `X-API-Version`
- Schema: версия в имени файла при breaking changes

## См. также

- `docs/architecture/production-backend.md` — сервисы и контракты
- `docs/architecture/monorepo.md` — структура monorepo
