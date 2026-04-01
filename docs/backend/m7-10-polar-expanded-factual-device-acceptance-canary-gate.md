# M7.10 - Polar-Expanded Factual Device Acceptance and Canary Gate

## Status

- Step ID: `M7.10`
- Status: `blocked`
- Date: `2026-03-30`
- Scope: factual acceptance/canary rerun for `M7.9` runtime bundle with mandatory `polar_rr` stream.

## Factual Run Metadata

- Acceptance bundle path: `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-10-polar-expanded-acceptance-canary-gate/`
- Report files:
  - `acceptance-gate-report.json`
  - `acceptance-gate-report.md`
  - `protocol-phase-trace.csv`
  - `websocket-inference-log.jsonl`
- Report experiment id: `m7-10-polar-expanded-acceptance-canary-gate-20260330T160939Z`
- Source mode: `live`
- Context: `internal_dashboard`
- WS URL: `ws://127.0.0.1:8120/ws/live`
- Health: `ok`, `model_loaded=true`

## Factual Summary

1. Rerun executed the same three protocol phases: `rest -> movement -> recovery`.
2. Sent streams are explicitly `watch_accelerometer`, `polar_hr`, `polar_rr` (all required `M7.9` primary streams present in traffic).
3. Sent `12` batches and captured `5` inference responses.
4. `error_count=0`; `heart_source=polar_hr` for all inferences.
5. Canary evidence is present for both tracks:
   - `activity_canary_present=true`
   - `arousal_canary_present=true`
6. Runtime telemetry was consistently present in inference payloads:
   - `feature_count_total=25`
   - `feature_count_nonzero=20`
   - `feature_coverage_by_track` present in all `5/5` responses.
7. Gate remains blocked because report confirms:
   - `real_device_evidence_present=false`
   - `device_protocol_validated=false`
   - `gate_decision=blocked`

## What Was Validated

1. `M7.9` bundle can run live inference with explicit `polar_rr` stream injection in acceptance flow.
2. `activity/arousal` canary fields are produced and serialized in factual artifacts.
3. Live websocket pipeline is stable in this run (`0` runtime errors).

## What Was Not Validated

1. Real paired physical-device execution evidence (`iPhone + Apple Watch + Polar H10`) linked to this acceptance run.
2. Device-side proof sufficient to set `real_device_evidence_present=true`.
3. Final claim-grade acceptance decision for production canary.

## Gate Decision

- Decision: `blocked`
- Reason: no physical-device evidence file was provided to the gate run.

## Next

`M7.10.1 - Physical-device evidence capture and factual rerun for M7.10 gate`
