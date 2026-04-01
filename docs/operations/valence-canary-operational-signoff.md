# Valence Canary Operational Sign-Off

## Scope

Документ фиксирует критерии допуска continuous internal-run после `E2.17`.

## Обязательные проверки

1. Scheduler cycle выполнен (`E2.13 + E2.15`).
2. Canary state обновлен и содержит актуальный `latest_check_utc`.
3. Dashboard snapshot обновлен и соответствует schema.
4. Runtime effective mode согласован со snapshot.
5. Runtime freshness check проходит по SLO.
6. CI contract-check проходит.
7. Alerting pipeline подключен и доступен оператору.

## Критерий допуска

Все пункты должны иметь статус `pass` в:

- `e2-17-end-to-end-canary-observability/signoff-checklist.csv`

Итоговый статус:

- `evaluation-report.json.decision = operational_signoff_ready`

## Burn-In Gate (E2.18)

Минимальный критерий:

1. минимум `3` последовательных цикла без ручных правок.
2. для всех циклов:
   - `effective_mode == policy_mode`,
   - `auto_disable=false`,
   - `alerts_count=0`,
   - `dashboard_fresh=true`,
   - шаги `E2.13/E2.15/contract-check` успешны.

Итог:

- `e2-18-continuous-run-burnin/burnin-decision-gate.json.decision = burnin_passed`

## Weekly Dry-Run Gate (E2.20)

Минимальный критерий:

1. Сформирован `weekly-summary-dry-run.md` с заполненными KPI.
2. Смоделированы оба triage-сценария:
   - `incident-warn-dry-run.md`,
   - `incident-critical-dry-run.md`.
3. `handoff-dry-run-checklist.csv` содержит только `pass`.
4. Pipeline checks (`E2.13/E2.15/contract-check`) успешны.

Итог:

- `e2-20-weekly-monitoring-dry-run/evaluation-report.json.decision = weekly_handoff_ready`

## Weekly Readiness Gate (E2.22)

Минимальный критерий:

1. Выполнен readiness review script `E2.22`.
2. `readiness-checklist.csv` содержит только `pass`.
3. Simulated weekly summary включает SLA/OLA-compliance поля.
4. E2.20 handoff readiness подтвержден как входной сигнал.

Итог:

- `e2-22-weekly-operations-readiness-review/evaluation-report.json.decision = steady_state_ready`
