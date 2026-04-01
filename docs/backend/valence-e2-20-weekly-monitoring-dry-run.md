# E2.20: Weekly Canary Monitoring Dry-Run

## Статус

- Parent track: `E2`
- Step: `E2.20`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Проверить на практике weekly monitoring flow из `E2.19`: weekly summary, triage по incident template и handoff decision.

## Что сделано

1. Добавлен reproducible dry-run script:
   - `scripts/ml/valence_e2_20_weekly_monitoring_dry_run.py`.
2. Выполнен dry-run weekly цикл:
   - `E2.13` canary check,
   - `E2.15` dashboard refresh,
   - contract-check (`validate_valence_canary_snapshot.py`).
3. Сформирован `E2.20` artifact bundle:
   - `evaluation-report.json`,
   - `weekly-summary-dry-run.md`,
   - `incident-warn-dry-run.md`,
   - `incident-critical-dry-run.md`,
   - `handoff-dry-run-checklist.csv`,
   - `scheduler-step-log.csv`,
   - `research-report.md`.
4. Dry-run результаты:
   - `decision = weekly_handoff_ready`,
   - `weekly_decision = investigate`,
   - `warn_triggered = true` (ожидаемо из-за неполного `7-day` окна),
   - `critical_triggered = false`,
   - `alerts_total = 0`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/`

## Ключевой результат

Weekly monitoring процесс operationally готов: шаблоны из `E2.19` реально отрабатываются end-to-end, triage-процедуры воспроизводимы, handoff decision формируется автоматически.

## Следующий шаг

`E2.21` — Weekly canary operations hardening:

1. формализовать retention policy для weekly artifacts и incidents;
2. добавить ownership rotation шаблон;
3. зафиксировать SLA/OLA для weekly triage completion.
