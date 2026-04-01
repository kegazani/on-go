# E2.21: Weekly Canary Operations Hardening

## Статус

- Parent track: `E2`
- Step: `E2.21`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Закрепить долгосрочные правила weekly эксплуатации canary-контура: retention, ownership rotation, SLA/OLA для triage/handoff.

## Что сделано

1. Зафиксирован operations policy:
   - `docs/operations/valence-canary-operations-hardening.md`.
2. Обновлен weekly summary template:
   - добавлены поля triage/handoff timestamps и compliance status.
3. Обновлен handoff pack:
   - добавлены требования weekly rotation и completion timestamps.
4. Обновлен operations runbook:
   - добавлена ссылка на hardening policy.

## Ключевые решения

1. Retention:
   - weekly summaries/checklists: `26` недель,
   - incidents/evaluation reports: `52` недели.
2. Ownership rotation:
   - weekly cadence (понедельник, UTC),
   - primary/secondary responsibility model.
3. SLA/OLA:
   - `critical`: triage `<=15m`, freeze/confirm `<=30m`, incident update `<=60m`;
   - `warn`: triage `<=4h`, weekly decision update `<=24h`;
   - weekly summary/handoff completion до конца weekly окна (`18:00/20:00 UTC`).

## Следующий шаг

`E2.22` — Weekly operations readiness review:

1. пройти checklist по новой policy на одном simulated weekly цикле;
2. проверить SLA/OLA-compliance полей в weekly summary;
3. зафиксировать final readiness decision для steady-state operations.
