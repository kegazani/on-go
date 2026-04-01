# M7.8 - P8 Acceptance and Claim Gate

## Status

- Step ID: `M7.8`
- Status: `blocked`
- Date: `2026-03-29`
- Scope: `P8` acceptance and claim gate after `P7` runtime integration.

## Factual Run Metadata

- Acceptance bundle path: `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-8-acceptance-claim-gate/`
- Report files:
  - `acceptance-gate-report.json`
  - `acceptance-gate-report.md`
  - `protocol-phase-trace.csv`
  - `websocket-inference-log.jsonl`
- Report experiment id: `m7-8-acceptance-claim-gate-20260329T175533Z`
- Generated at UTC: `2026-03-29T17:55:33.484554+00:00`
- Source mode: `live`
- Context: `internal_dashboard`
- WS URL: `ws://127.0.0.1:8120/ws/live`
- Health: `ok`, `model_loaded=true`

## Factual Summary

1. The run executed three protocol phases in order: `rest`, `movement`, `recovery`.
2. The gate sent `12` batches total and received `5` inference messages.
3. There were `0` errors and `0` pong messages.
4. All received inferences used `heart_source=polar_hr` with `heart_source_fallback_active=false`.
5. Every inference reported:
   - `feature_count_total=25`
   - `feature_count_nonzero=20`
   - `claim_level=safe`
   - `confidence_score=0.85`
   - `derived_state=calm_rest`
6. The trace shows the same missing feature set in each inference payload:
   - `watch_bvp_c0__last`
   - `watch_bvp_c0__max`
   - `watch_bvp_c0__mean`
   - `watch_bvp_c0__min`
   - `watch_bvp_c0__std`
7. The JSON report explicitly sets:
   - `gate_decision=blocked`
   - `device_protocol_validated=false`
   - `real_device_evidence_present=false`
   - `decision_reason=No real physical-device evidence was present in this run.`

## What Was Validated

1. The websocket runtime path is producing structured inference telemetry in the expected format.
2. Phase ordering and message handling are stable across the three requested phases.
3. Telemetry counters are present in both the report and the trace artifacts.
4. The acceptance gate remains conservative because the report does not prove a real physical-device execution.

## What Was Not Validated

1. Real iPhone + Apple Watch + Polar H10 protocol execution.
2. Physical-device session stability for 10+ minutes.
3. Rest/movement/recovery transitions on actual hardware.
4. Device-side evidence sufficient to set `device_protocol_validated=true`.

## Gate Decision

- Decision: `blocked`
- Reason: the acceptance report says `device_protocol_validated=false` and `real_device_evidence_present=false`.
- Policy outcome: keep `M7.8` blocked and advance to a factual physical-device acceptance run as the next step.

## Next

`M7.8.1 - factual physical-device acceptance run`
