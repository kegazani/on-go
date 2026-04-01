# Backend Monorepo

Этот репозиторий предназначен для backend-части многомодульной системы.
Каждый самостоятельный бизнес-функционал оформляется как отдельный сервис,
но все backend-сервисы, контракты и инфраструктурные артефакты хранятся в одном репозитории.

Swift-фронтенд должен жить в отдельном репозитории.

Рекомендуемая структура рабочих репозиториев:

```text
workspace/
  on-go/          # backend monorepo
  on-go-ios/      # отдельный Swift/iOS репозиторий
```

Структура backend monorepo:

```text
.
├── contracts/        # API и event-контракты
├── docs/             # архитектурные документы и ADR
├── infra/            # локальная и целевая инфраструктура
├── platform/         # общие платформенные модули
├── scripts/          # служебные скрипты
└── services/         # отдельные backend-сервисы
```

Принципы:

1. Один бизнес-контекст = один сервис.
2. Общие контракты не копируются между сервисами, а хранятся централизованно.
3. Общий код выносится только в стабильные платформенные модули, без лишней связности.
4. Swift-клиент интегрируется через опубликованные контракты и SDK, но не входит в этот репозиторий.

Дальше логично делать так:

1. Выбрать базовый стек сервисов.
2. Создать шаблон первого сервиса.
3. Добавить локальный запуск через `docker compose` или другой orchestrator.
4. Настроить генерацию контрактов для Swift-клиента.

Подробный roadmap по фазам исследования, ML pipeline и backend:

- `docs/roadmap/research-pipeline-backend-plan.md`

Рабочий протокол и статус выполнения:

- `docs/process/collaboration-protocol.md`
- `docs/status/execution-status.md`
- `docs/status/work-log.md`

Документы исследовательской фазы:

- `docs/research/research-protocol.md`
- `docs/research/session-data-schema.md`
- `docs/research/label-specification.md`
- `docs/research/evaluation-plan.md`
- `docs/research/model-reporting-standard.md`
- `docs/research/personalization-user-profile-schema.md`
- `docs/research/personalization-methodology-redesign.md`
- `docs/research/personalization-realtime-evaluation-plan.md`
- `docs/research/f1-equals-one-analysis.md`

Документы dataset-фазы:

- `docs/datasets/external-datasets-f1-prioritization.md`
- `docs/datasets/dataset-registry-format.md`
- `docs/datasets/external-datasets-onboarding-runbook.md`

Локальная структура внешних данных:

- `data/external/README.md`

Документы capture-фазы:

- `docs/capture/swift-repository-structure.md`
- `docs/capture/device-e2e-validation-runbook.md`
- `docs/capture/hkworkoutsession-migration-design.md`

Локальный Docker и подключение приложения:

- `docs/setup/local-docker-setup.md`

Документы backend-фаз:

- `docs/backend/raw-ingest-c1.md`
- `docs/backend/raw-ingest-c2.md`
- `docs/backend/raw-ingest-c3.md`
- `docs/backend/raw-ingest-c4.md`
- `docs/backend/replay-d1.md`
- `docs/backend/replay-d2.md`
- `docs/backend/replay-d3.md`
- `docs/backend/signal-processing-e1.md`
- `docs/backend/signal-processing-e2.md`
- `docs/backend/datasets-f2.md`
- `docs/backend/datasets-f2-1.md`
- `docs/backend/datasets-f2-2.md`
- `docs/backend/datasets-f2-3.md`
- `docs/backend/modeling-g1.md`
- `docs/backend/modeling-g2.md`
- `docs/backend/modeling-g3.md`
- `docs/backend/modeling-g3-1.md`
- `docs/backend/modeling-g3-2.md`
- `docs/backend/personalization-h1.md`
- `docs/backend/personalization-h2.md`
- `docs/backend/personalization-h3.md`
- `docs/backend/personalization-h4.md`
- `docs/backend/personalization-h5.md`
- `docs/backend/personalization-h6.md`
- `docs/backend/research-gate-i1.md`
- `docs/backend/personalization-i1-1.md`

HTTP-контракты backend ingest:

- `contracts/http/raw-session-ingest.openapi.yaml`
- `contracts/http/raw-session-replay.openapi.yaml`
- `contracts/http/inference-api.openapi.yaml`
- `contracts/http/personalization-worker.openapi.yaml`
- `contracts/http/live-inference-api.openapi.yaml`
- `contracts/personalization/user-profile.schema.json`
- `contracts/personalization/personalization-feature-contract.schema.json`

Архитектура production backend:

- `docs/architecture/production-backend.md`

Operations (K3):

- `docs/operations/runbook.md`

Сервисы backend:

- `services/ingest-api/README.md`
- `services/replay-service/README.md`
- `services/signal-processing-worker/README.md`
- `services/dataset-registry/README.md`
- `services/modeling-baselines/README.md`
- `services/inference-api/README.md`
- `services/personalization-worker/README.md`
- `services/live-inference-api/README.md`
