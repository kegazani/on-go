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

Документы capture-фазы:

- `docs/capture/swift-repository-structure.md`
- `docs/capture/device-e2e-validation-runbook.md`
- `docs/capture/hkworkoutsession-migration-design.md`

Локальный Docker и подключение приложения:

- `docs/setup/local-docker-setup.md`

Документы backend-фаз:

- `docs/backend/raw-ingest-c1.md`
- `docs/backend/raw-ingest-c2.md`
- `docs/backend/replay-d1.md`
- `docs/backend/signal-processing-e1.md`

HTTP-контракты backend ingest:

- `contracts/http/raw-session-ingest.openapi.yaml`
- `contracts/http/raw-session-replay.openapi.yaml`

Сервисы backend:

- `services/ingest-api/README.md`
- `services/replay-service/README.md`
- `services/signal-processing-worker/README.md`
