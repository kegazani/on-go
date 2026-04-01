# GitHub Workflows

## ci.yml (K3)

- **contract-checks** — schema validation для `valence-canary-dashboard` snapshot
- **unit-tests** — pytest для ingest-api, replay-service, signal-processing-worker, dataset-registry, modeling-baselines
- **stack-e2e** — docker compose up, replay integration tests

Триггер: push/PR в main.

## valence-canary-check.yml (E2.15)

- **canary-check** — hourly scheduler для `E2.13` (`valence_e2_13_canary_hardening.py`) и snapshot refresh `E2.15` (`valence_e2_15_scheduler_dashboard.py`)
- Загружает canary артефакты как GitHub Actions artifact.

Триггер: `schedule` (каждый час) + `workflow_dispatch`.

## Планируется

1. Валидация контрактов (OpenAPI)
2. Сборка и публикация артефактов
3. Деплой по окружениям
