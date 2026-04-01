# Valence Scoped Policy Runbook

## Scope

Этот runbook описывает операционный режим `internal_scoped` для `valence` (не user-facing).

## Preconditions

1. Актуальный decision из `E2.9` подтверждает scoped-кандидат.
2. Загружен policy-файл по контракту:
   - `contracts/personalization/valence-scoped-policy.schema.json`
3. Все guardrails установлены в `false` для user-facing use:
   - `user_facing_claims`
   - `risk_notifications`
   - `auto_personalization_trigger`

## Enable Procedure

1. Применить policy из:
   - `data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/scoped-policy.json`
2. Включить только контексты:
   - `research_only`
   - `internal_dashboard`
   - `shadow_mode`
3. Проверить, что публичные каналы не получают `valence` decisions.

## Monitoring

Ключевые KPI:

1. `wesad_to_grex_macro_f1`
2. `grex_to_wesad_macro_f1`
3. `unknown_rate_after_gate`
4. `prediction_volume_daily`

Source:

- `monitoring-kpis.csv` в `e2-10-valence-operational-gate/`.

## Rollback Rules

Отключить scoped режим при любом trigger:

1. `wesad_to_grex_macro_f1 < 0.32`
2. `grex_to_wesad_macro_f1 < 0.40`
3. `unknown_rate_after_gate > 0.50`

Source:

- `rollback-triggers.csv` в `e2-10-valence-operational-gate/`.

## Exit Criteria

1. scoped режим стабилен минимум `N` последовательных evaluation циклов (задается отдельно).
2. нет rollback событий.
3. decision-gate обновлен и подтвержден для следующего этапа (`E2.11+`).

## E2.13 Canary Hardening

Периодический runtime-check:

1. Запускать:
   - `python3 scripts/ml/valence_e2_13_canary_hardening.py --check-interval-minutes 60`
2. Проверять `canary-state.json`:
   - `auto_disable=false` для нормального режима;
   - при `auto_disable=true` effective mode должен считаться `disabled`.
3. Для runtime-интеграции выставить:
   - `INFERENCE_VALENCE_CANARY_STATE_PATH=/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/canary-state.json`
4. Alerting source:
   - `alerts.json` и `canary-state.json.alerts`.

## E2.14 Drill and Recovery SLA

Drill-команда:

1. `python3 scripts/ml/valence_e2_14_canary_drill.py`

Ожидаемое подтверждение rollback-path:

1. `runtime-drill-confirmation.json` должен показывать:
   - `baseline_effective_mode=internal_scoped`
   - `drill_effective_mode=disabled`
2. `evaluation-report.json.decision` должен быть `rollback_path_confirmed`.

Recovery SLA (target RTO `80 min`):

1. `detect_trigger` — до `5` минут.
2. `operator_ack` — до `10` минут.
3. `rollback_execution` — до `5` минут.
4. `stability_observation` — `60` минут.

## E2.16 Runtime Dashboard Endpoint

Runtime endpoint:

1. `GET /v1/monitoring/valence-canary`

Health freshness fields:

1. `valence_dashboard_snapshot_loaded`
2. `valence_dashboard_fresh`

SLO:

1. `INFERENCE_VALENCE_DASHBOARD_FRESHNESS_SLO_MINUTES=120` (по умолчанию).
