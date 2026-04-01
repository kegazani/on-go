# Valence Canary Handoff Pack

## Scope

Этот документ фиксирует правила передачи и регулярного сопровождения canary-контура после `E2.19`.

## Ownership

1. Primary owner: `ML/Inference on-call`.
2. Secondary owner: `Backend operations`.
3. Escalation owner (`critical`): `Runtime incident commander`.
4. Rotation cadence: weekly (понедельник, UTC), с обязательным подтверждением передачи.

## Cadence

1. Hourly: scheduler/check-job (`E2.13 + E2.15` path).
2. Daily: quick triage по alerts и freshness.
3. Weekly: заполнение `valence-canary-weekly-summary.md`.

## Mandatory Inputs for Weekly Review

1. Последний `canary-state`.
2. Dashboard snapshot history за 7 дней.
3. Alert history за 7 дней.
4. Runtime health/freshness snapshots.
5. Incident records (если были).

## Weekly Handoff Checklist

1. Все KPI в weekly summary заполнены.
2. `auto_disable_events == 0` или приложен incident.
3. Все `critical` события закрыты или есть active mitigation plan.
4. Следующая weekly ownership смена подтверждена.
5. Поля `triage_started_at_utc/triage_completed_at_utc/handoff_completed_at_utc` заполнены.

## Triage Policy

1. Если `warn`:
   - создать triage task,
   - назначить owner,
   - проверить повторяемость в следующем цикле.
2. Если `critical`:
   - немедленно перевести effective mode в `disabled` (если еще не),
   - открыть incident по шаблону `valence-canary-incident-template.md`,
   - выполнить recovery validation до возврата в `internal_scoped`.

## Handoff Output

По итогам weekly handoff должны быть обновлены:

1. `valence-canary-weekly-summary.md`
2. incident record (если применимо)
3. decision note: `keep_internal_scoped` или `freeze_to_disabled`
4. ссылка на policy: `valence-canary-operations-hardening.md`
