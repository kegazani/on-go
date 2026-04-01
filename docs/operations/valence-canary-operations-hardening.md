# Valence Canary Weekly Operations Hardening (E2.21)

## Scope

Документ фиксирует operational baseline для регулярного weekly triage/handoff после `E2.20`.

## Retention Policy

1. Weekly summaries (`weekly-summary*.md`): хранить минимум `26` недель.
2. Incident records (`incident-*.md`): хранить минимум `52` недели.
3. Checklist/step logs (`handoff-*.csv`, `scheduler-step-log.csv`): хранить минимум `26` недель.
4. `evaluation-report.json` для weekly runs: хранить минимум `52` недели.
5. Очистка старых артефактов выполняется только после успешного monthly backup.

## Ownership Rotation

1. Rotation cadence: еженедельно (каждый понедельник, UTC).
2. Роли:
   - `primary_oncall` (ведет weekly summary, принимает решение),
   - `secondary_oncall` (проверяет triage и закрытие action items).
3. Передача ownership обязательна только после заполненного handoff checklist.
4. Если передача не подтверждена до `12:00 UTC` понедельника:
   - ownership остается у текущего primary,
   - создается `warn` triage task.

## SLA / OLA

### SLA (внешние обязательства внутри internal scope)

1. Для `critical` события:
   - triage start: не позже `15` минут от detection,
   - mode freeze (`disabled`) или подтверждение existing freeze: не позже `30` минут,
   - initial incident update: не позже `60` минут.

2. Для `warn` события:
   - triage start: не позже `4` часов,
   - weekly decision update: не позже `24` часов.

### OLA (внутренние операционные соглашения)

1. Weekly summary completion: до `18:00 UTC` последнего дня weekly окна.
2. Handoff checklist completion: до `20:00 UTC` того же дня.
3. Open action items должны иметь owner и due-date до закрытия weekly handoff.

## Compliance Checks

1. Каждая weekly запись должна содержать:
   - `prepared_at_utc`,
   - `triage_started_at_utc`,
   - `triage_completed_at_utc`,
   - `handoff_completed_at_utc`.
2. Для любого `critical` обязательна incident карточка.
3. Для любого `warn` без инцидента обязателен triage task id в weekly summary.

## Escalation

1. SLA miss по `critical` -> немедленная эскалация `runtime incident commander`.
2. Два подряд weekly OLA misses -> пересмотр ownership rotation и capacity.
