# E2.15: Canary Scheduler and Dashboard Contract

## Статус

- Parent track: `E2`
- Step: `E2.15`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Формализовать регулярный запуск canary-check и dashboard-friendly snapshot contract для continuous internal rollout.

## Что сделано

1. Добавлен scheduler wiring:
   - GitHub Actions workflow `valence-canary-check.yml` (hourly + manual).
   - cron spec `infra/ops/valence-canary/cron/valence-canary-check.cron`.
   - systemd service/timer для hourly запуска.
2. Добавлен dashboard snapshot schema:
   - `contracts/operations/valence-canary-dashboard.schema.json`.
3. Добавлен сборщик scheduler/dashboard артефактов:
   - `scripts/ml/valence_e2_15_scheduler_dashboard.py`.
4. Сформирован artifact bundle `E2.15`:
   - `dashboard-snapshot.json`,
   - `scheduler-spec.json`,
   - `acceptance-checklist.csv`,
   - `evaluation-report.json`,
   - `research-report.md`.
5. Добавлена operations-документация scheduler:
   - `docs/operations/valence-canary-scheduler.md`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/`

Файлы:

1. `evaluation-report.json`
2. `dashboard-snapshot.json`
3. `scheduler-spec.json`
4. `acceptance-checklist.csv`
5. `research-report.md`

## Ключевой результат

Scheduler + dashboard контракт готовы: регулярный hourly check формализован, snapshot имеет стабильную схему, acceptance checklist пройден (`6/6`, `overall_status=ready`).

## Следующий шаг

`E2.16` — Runtime dashboard endpoint integration:

1. отдать dashboard snapshot через отдельный runtime endpoint;
2. добавить lightweight schema checks в CI;
3. зафиксировать операционные SLO для canary dashboard freshness.
