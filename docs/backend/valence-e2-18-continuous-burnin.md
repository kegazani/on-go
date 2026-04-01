# E2.18: Continuous-Run Burn-In

## Статус

- Parent track: `E2`
- Step: `E2.18`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Подтвердить стабильность canary-контура в серии последовательных scheduler-циклов без ручных правок и зафиксировать burn-in decision gate.

## Что сделано

1. Добавлен burn-in скрипт:
   - `scripts/ml/valence_e2_18_continuous_burnin.py`
2. Выполнено `3` последовательных цикла:
   - `E2.13` canary check,
   - `E2.15` dashboard refresh,
   - contract check.
3. По каждому циклу проверены:
   - `effective_mode`,
   - `auto_disable`,
   - `alerts_count`,
   - `dashboard_fresh`,
   - успешность шагов pipeline.
4. Сформирован burn-in decision gate:
   - `burnin-decision-gate.json`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-18-continuous-run-burnin/`

Файлы:

1. `evaluation-report.json`
2. `burnin-decision-gate.json`
3. `burnin-cycle-summary.csv`
4. `burnin-step-log.csv`
5. `research-report.md`

## Ключевой результат

Burn-in завершен успешно: все циклы стабильны и соответствуют критериям (`burnin_passed`), контур готов к длительному continuous internal-run.

## Следующий шаг

`E2.19` — Long-horizon canary monitoring pack:

1. добавить weekly summary aggregation для burn-in/history;
2. формализовать incident-template для rollback случаев;
3. подготовить handoff-пакет для длительной эксплуатации.
