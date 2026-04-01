# E2.14: Canary Drill and Rollback Simulation

## Статус

- Parent track: `E2`
- Step: `E2.14`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Проверить rollback-path в контролируемом forced-trigger сценарии и подтвердить, что runtime автоматически переходит в `disabled` через canary-state.

## Что сделано

1. Добавлен drill-скрипт:
   - `scripts/ml/valence_e2_14_canary_drill.py`
2. Выполнен forced rollback drill:
   - искусственно нарушены rollback-пороги на последнем цикле;
   - сгенерированы `drill-canary-state` и `drill-alerts`.
3. Выполнено runtime-подтверждение:
   - baseline effective mode: `internal_scoped`;
   - drill effective mode: `disabled`.
4. Зафиксированы recovery-процедура и SLA:
   - `target_rto_minutes=80`,
   - пошаговый recovery flow после auto-disable.
5. Обновлен operations runbook по drill/recovery.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/`

Файлы:

1. `evaluation-report.json`
2. `runtime-drill-confirmation.json`
3. `drill-canary-state.json`
4. `drill-alerts.json`
5. `drill-shadow-cycle-metrics.csv`
6. `drill-trigger-results.csv`
7. `recovery-sla.json`
8. `research-report.md`

## Ключевой результат

Rollback-path подтвержден (`rollback_path_confirmed`): forced trigger включает `auto_disable=true`, и runtime переключает effective mode на `disabled` без изменения основной policy.

## Следующий шаг

`E2.15` — Canary scheduler and dashboard contract:

1. добавить scheduler wiring (cron/systemd/CI job spec) для `E2.13` checks;
2. зафиксировать dashboard-friendly snapshot contract для canary-state/alerts;
3. подготовить acceptance checklist для continuous internal rollout.
