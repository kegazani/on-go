# E2.17: End-to-End Canary Observability Drill

## Статус

- Parent track: `E2`
- Step: `E2.17`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Проверить полный контур observability: scheduler -> canary-state -> runtime dashboard endpoint -> CI contract-check и сформировать operational sign-off.

## Что сделано

1. Добавлен e2e drill скрипт:
   - `scripts/ml/valence_e2_17_observability_drill.py`
2. В одном запуске выполнены:
   - `E2.13` canary check,
   - `E2.15` dashboard snapshot refresh,
   - contract validation (`validate_valence_canary_snapshot.py`).
3. Подтверждена runtime консистентность:
   - effective mode в runtime совпадает со snapshot,
   - freshness проходит по SLO.
4. Сформирован sign-off пакет:
   - `signoff-checklist.csv`,
   - `scheduler-run-log.json`,
   - `runtime-endpoint-response.json`,
   - `evaluation-report.json`.
5. Добавлен operations sign-off документ:
   - `docs/operations/valence-canary-operational-signoff.md`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-17-end-to-end-canary-observability/`

Файлы:

1. `evaluation-report.json`
2. `signoff-checklist.csv`
3. `scheduler-run-log.json`
4. `runtime-endpoint-response.json`
5. `research-report.md`

## Ключевой результат

Observability chain подтверждена end-to-end; operational sign-off готов к continuous internal-run.

## Следующий шаг

`E2.18` — Continuous-run burn-in:

1. выполнить серию последовательных scheduler-циклов (`>=3`) без ручных правок;
2. проверить стабильность freshness/alerts/effective-mode по всем циклам;
3. зафиксировать финальный burn-in decision gate.
