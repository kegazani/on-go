# Valence Canary Scheduler

## Цель

Описать регулярный запуск canary-check и публикацию dashboard snapshot для scoped `valence`.

## Scheduler wiring

Поддерживаются три варианта:

1. GitHub Actions:
   - `.github/workflows/valence-canary-check.yml`
   - запуск каждый час (`0 * * * *`) + ручной `workflow_dispatch`.
2. Cron:
   - `infra/ops/valence-canary/cron/valence-canary-check.cron`
3. systemd:
   - `infra/ops/valence-canary/systemd/valence-canary-check.service`
   - `infra/ops/valence-canary/systemd/valence-canary-check.timer`

## Pipeline шага

1. `python3 scripts/ml/valence_e2_13_canary_hardening.py --check-interval-minutes 60`
2. `python3 scripts/ml/valence_e2_15_scheduler_dashboard.py`

## Dashboard contract

Snapshot должен соответствовать:

- `contracts/operations/valence-canary-dashboard.schema.json`

Ключевой snapshot artifact:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/dashboard-snapshot.json`

## Alerting

Alert source:

1. `e2-13-valence-canary-hardening/alerts.json`
2. `e2-13-valence-canary-hardening/canary-state.json` (`alerts`, `auto_disable`)

Если `auto_disable=true`, runtime должен воспринимать effective mode как `disabled`.
