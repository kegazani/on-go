# Valence Canary Steady-State Kickoff (E2.23)

## Scope

Документ фиксирует старт регулярного weekly operations режима после `steady_state_ready`.

## Weekly Cadence Window (UTC)

1. Weekly monitoring window: `Monday 00:00` -> `Sunday 23:59`.
2. Weekly triage summary deadline: `Sunday 18:00`.
3. Weekly handoff completion deadline: `Sunday 20:00`.
4. Ownership rotation confirmation: `Monday 12:00`.

## Initial 3-Week Ownership Roster

| Week (UTC) | Window | Primary On-call | Secondary On-call | Escalation Commander |
| --- | --- | --- | --- | --- |
| `2026-W14` | `2026-03-30 .. 2026-04-05` | `ML/Inference On-call A` | `Backend Ops A` | `Runtime IC A` |
| `2026-W15` | `2026-04-06 .. 2026-04-12` | `ML/Inference On-call B` | `Backend Ops B` | `Runtime IC B` |
| `2026-W16` | `2026-04-13 .. 2026-04-19` | `ML/Inference On-call C` | `Backend Ops C` | `Runtime IC C` |

## Weekly Handoff Checkpoints

1. `T0 (Monday 00:00)` — новый weekly window открыт.
2. `T1 (Daily)` — quick triage по alerts/freshness.
3. `T2 (Sunday 18:00)` — weekly summary finalized.
4. `T3 (Sunday 20:00)` — handoff checklist completed.
5. `T4 (Monday <=12:00)` — ownership rotation подтверждена.

## Required Artifacts per Week

1. `weekly-summary.md` (или эквивалент weekly output).
2. `handoff checklist` c заполненными timestamps.
3. Incident record (если были `warn/critical`).
4. Weekly decision note (`keep_internal_scoped / investigate / freeze_to_disabled`).

## Kickoff Decision

Steady-state weekly режим запускается с `2026-W14` и действует до пересмотра policy.
