# Production Backend Architecture (K1)

Документ фиксирует целевую архитектуру production backend и пути миграции от текущего research-режима.

## Цель

Система стабильно принимает записи, обрабатывает их, выдаёт инференс и поддерживает персонализацию без ручного вмешательства исследовательской команды.

## Сервисы

| Сервис | Назначение | Статус |
| --- | --- | --- |
| `ingest-api` | Приём raw session package, presign, finalize | ✅ Реализован |
| `replay-service` | Replay manifest, windows, SSE orchestration | ✅ Реализован |
| `signal-processing-worker` | Sync, clean, quality flags, feature extraction | ✅ Реализован |
| `dataset-registry` | Импорт external datasets, registry metadata | ✅ Реализован |
| `modeling-baselines` | Training, evaluation, MLflow tracking | ✅ Реализован |
| `inference-api` | Online inference, model serving | ✅ K2 |
| `live-inference-api` | WebSocket streaming inference | Live streaming |
| `personalization-worker` | Calibration, adaptation, profile update | K4 |
| `training-orchestrator` | Job queue, dataset build, training runs | Планируется |
| `model-registry` | Versioned model storage, promotion | MLflow-based (J1) |

## Контуры: online и offline

### Online (latency-sensitive)

- `ingest-api` — приём сессий от capture app
- `inference-api` — предсказания `activity/arousal` по streaming features, scoped `valence` guardrails и semantic output layer для `derived_state`
- `personalization-worker` (real-time path) — calibration update, profile read

### Offline (batch, async)

- `signal-processing-worker` — preprocessing raw → clean → features
- `dataset-registry` — импорт внешних датасетов
- `modeling-baselines` — training, evaluation
- `personalization-worker` (batch path) — full refit, adaptation

### Гибрид

- `replay-service` — используется для live replay и offline replay validation на записанных сессиях; simulated capture не является поддерживаемым режимом

## Потоки данных

```text
[Capture App] → ingest-api → Postgres + MinIO (raw)
                    ↓
           signal-processing-worker (по триггеру или cron)
                    ↓
              MinIO (clean, features)
                    ↓
           inference-api ← [Model Registry]
                    ↓
              [Client / Replay]
```

## Контракты

### HTTP

| Контракт | Сервис | Файл |
| --- | --- | --- |
| Raw Session Ingest | ingest-api | `contracts/http/raw-session-ingest.openapi.yaml` |
| Raw Session Replay | replay-service | `contracts/http/raw-session-replay.openapi.yaml` |

### Event (планируется K2)

- `session.ingested` — после finalize
- `session.processed` — после preprocessing
- `model.promoted` — после выкладки новой модели

### Schema

| Схема | Назначение |
| --- | --- |
| `contracts/personalization/user-profile.schema.json` | Профиль пользователя |
| `contracts/personalization/personalization-feature-contract.schema.json` | Feature contract для персонализации |

### K5 semantic contract (K5.1 baseline)

- Canonical direct outputs:
  - `activity_class`
  - `arousal_coarse`
  - `valence_coarse` (только при passed scoped policy)
- Canonical derived outputs:
  - `derived_state`
  - `confidence`
  - `fallback_reason`
  - `claim_level`
- Decision table и claim boundaries зафиксированы в:
  - `docs/backend/state-semantics-derived-state-contract.md`
  - `contracts/operations/derived-state-semantics.schema.json`

## Инфраструктура

### Текущая (docker compose)

- Postgres, MinIO, ingest-api, replay-service
- Локальный запуск: `scripts/run-stack.sh` / `docker compose -f infra/compose/on-go-stack.yml up`

### Целевая (production)

- Отдельные окружения: dev, staging, prod
- Redis в стеке (K2) — очередь для offline workers
- Observability: метрики, трейсы, алерты
- CI/CD: тесты, деплой, rollback

## Auth и audit

- Ingest: опциональный API key (`ON_GO_INGEST_AUTH_TOKEN`)
- Audit: `ingest_audit_log` в Postgres
- Полноценный auth (OAuth2/JWT) — на этапе K3

## Миграция

1. **K1** — зафиксировать архитектуру (этот документ), формализовать контракты
2. **K2** — inference-api, очереди, async processing
3. **K3** — deployment, observability, operations
4. **K5** — semantic outputs и derived-state contract поверх `activity/arousal/scoped valence`

## Ссылки

- Roadmap: `docs/roadmap/research-pipeline-backend-plan.md`
- Monorepo: `docs/architecture/monorepo.md`
- Docker stack: `infra/compose/on-go-stack.yml`
