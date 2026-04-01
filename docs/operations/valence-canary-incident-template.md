# Valence Canary Incident Template

## Header

- Incident ID: `<VAL-CANARY-YYYYMMDD-###>`
- Severity: `<warn/critical>`
- Status: `<open/mitigated/resolved>`
- Opened at (UTC): `<timestamp>`
- Owner: `<name>`

## Trigger

- Trigger source: `<scheduler/runtime/dashboard/ci>`
- Trigger type: `<auto_disable/freshness_slo_violation/effective_mode_drift/alert_spike>`
- First detected at (UTC): `<timestamp>`
- Detection artifact: `<path or link>`

## Impact

- Affected scope: `<internal_dashboard/research/runtime>`
- Effective mode at incident start: `<internal_scoped/disabled>`
- User-facing impact: `<none/internal_only/needs_followup>`
- Duration: `<minutes>`

## Timeline

| Time (UTC) | Event |
| --- | --- |
| `<t0>` | `<detection>` |
| `<t1>` | `<triage started>` |
| `<t2>` | `<mitigation applied>` |
| `<t3>` | `<recovery validated>` |

## Mitigation

1. Immediate action:
   - `<freeze mode / disable rollout / scheduler pause>`
2. Validation checks:
   - `<dashboard fresh>`
   - `<effective mode consistent>`
   - `<alerts stabilized>`

## Root Cause

- Category: `<data gap / scheduler fault / policy mismatch / runtime regression / unknown>`
- Hypothesis: `<short explanation>`
- Confirmed evidence: `<path or link>`

## Corrective Actions

1. `<action with owner and due date>`
2. `<action with owner and due date>`

## Exit Criteria

- `critical` triggers cleared.
- Latest cycle `pass`.
- Weekly decision updated in summary.

## Postmortem

- Final decision: `<keep_internal_scoped / keep_disabled_until_fix>`
- Lessons learned:
  1. `<lesson 1>`
  2. `<lesson 2>`
