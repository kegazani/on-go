# E2.10: Scoped Valence Policy Operational Hardening

## Статус

- Parent track: `E2`
- Step: `E2.10`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Перевести результаты `E2.9` в операционно управляемую policy-конфигурацию с guardrails, rollback-триггерами и decision-gate артефактами.

## Что сделано

1. Добавлен контракт scoped policy:
   - `contracts/personalization/valence-scoped-policy.schema.json`.
2. Добавлен автоматический gate-скрипт:
   - `scripts/ml/valence_e2_10_operational_gate.py`.
3. На основе `E2.9` sensitivity сформирован policy-пакет:
   - mode: `internal_scoped`,
   - model: `ridge_classifier`,
   - floor: `0.35`,
   - strict non-user-facing guardrails.
4. Сформированы monitoring/rollback artifacts.
5. Добавлен операционный runbook:
   - `docs/operations/valence-scoped-policy-runbook.md`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/`

Файлы:

1. `scoped-policy.json`
2. `evaluation-report.json`
3. `monitoring-kpis.csv`
4. `rollback-triggers.csv`
5. `research-report.md`

## Ключевое решение

1. Global user-facing режим остается запрещен.
2. Разрешен только `internal_scoped` режим:
   - contexts: `research_only`, `internal_dashboard`, `shadow_mode`.
3. Авто-триггеры персонализации по `valence` отключены.

## Следующий шаг

`E2.11` — Scoped mode runtime integration:

1. добавить contract-level flags в inference/runtime слой;
2. подключить policy loader и hard guardrails в сервисах;
3. провести dry-run включения/отключения scoped режима.
