# Valence Canary Weekly Summary

## Period

- Week (UTC): `<YYYY-Www>`
- Window: `<YYYY-MM-DD> .. <YYYY-MM-DD>`
- Prepared at (UTC): `<timestamp>`
- Owner: `<name>`
- Triage started at (UTC): `<timestamp>`
- Triage completed at (UTC): `<timestamp>`
- Handoff completed at (UTC): `<timestamp>`
- Triage task / incident id: `<id or n/a>`

## Source Artifacts

1. Latest dashboard snapshots (`valence-canary-dashboard`).
2. Canary state history (`canary-state` / check logs).
3. Alert events (`alerts.json` or equivalent sink).
4. Runtime health snapshots (`/health` freshness fields).

## Weekly KPI

| KPI | Value | Threshold | Status |
| --- | --- | --- | --- |
| `cycles_total` | `<n>` | `>= 7` | `<pass/warn/fail>` |
| `cycles_pass_rate` | `<0..1>` | `>= 0.95` | `<pass/warn/fail>` |
| `alerts_total` | `<n>` | `<= 1 warn / 0 critical` | `<pass/warn/fail>` |
| `auto_disable_events` | `<n>` | `0` | `<pass/fail>` |
| `freshness_slo_violations` | `<n>` | `0` | `<pass/fail>` |
| `effective_mode_drift_events` | `<n>` | `0` | `<pass/fail>` |

## Observations

1. `<key observation #1>`
2. `<key observation #2>`
3. `<key observation #3>`

## Decisions

- Weekly decision: `<keep_internal_scoped / freeze_to_disabled / investigate>`
- Reason: `<short reason>`
- Required actions before next week:
  1. `<action 1>`
  2. `<action 2>`

## Escalation Check

- `warn` condition triggered: `<yes/no>`
- `critical` condition triggered: `<yes/no>`
- Incident created: `<incident_id or n/a>`

## Compliance

- SLA/OLA status: `<pass/warn/fail>`
- Retention class: `weekly_summary_26w`
