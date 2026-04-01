# E2.12: Scoped Mode Shadow-Cycle Evaluation

## Статус

- Parent track: `E2`
- Step: `E2.12`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Проверить устойчивость `internal_scoped` режима для `valence` в серии shadow/replay циклов и принять операционное решение по rollback-gate.

## Что сделано

1. Добавлен скрипт `scripts/ml/valence_e2_12_shadow_cycle_evaluation.py`.
2. Выполнена оценка 5 shadow-циклов с KPI и rollback-checks:
   - `wesad_to_grex_macro_f1`
   - `grex_to_wesad_macro_f1`
   - `unknown_rate_after_gate`
   - `prediction_volume_daily`
3. Подтверждена runtime-изоляция контекстов:
   - разрешены `research_only/internal_dashboard/shadow_mode`;
   - `public_app` остается заблокирован.
4. Сформирован decision gate:
   - rollback событий `0`;
   - итоговый режим: `keep_internal_scoped`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-12-valence-shadow-cycle-evaluation/`

Файлы:

1. `evaluation-report.json`
2. `shadow-cycle-metrics.csv`
3. `rollback-check-results.csv`
4. `research-report.md`

## Ключевой результат

Scoped `valence` режим сохраняется в `internal_scoped` при текущих guardrails: во всех shadow-циклах KPI остались выше rollback-порогов, а user-facing контекст по-прежнему блокируется.

## Следующий шаг

`E2.13` — Scoped mode canary hardening:

1. добавить periodical runtime-check job для автоматического расчета rollback KPI;
2. связать rollback conditions с alerting и auto-disable flag;
3. зафиксировать canary readiness checklist для controlled rollout внутри internal контуров.
