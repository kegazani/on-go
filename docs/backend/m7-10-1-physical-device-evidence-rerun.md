# M7.10.1 - Physical-Device Evidence Rerun

## Status

- Step ID: `M7.10.1`
- Status: `blocked`
- Date: `2026-03-30`
- Scope: factual rerun for `M7.10` with explicit check of `--real-device-evidence`.

## Factual Run Metadata

- Acceptance bundle path: `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-10-1-physical-device-evidence-rerun/`
- Report files:
  - `acceptance-gate-report.json`
  - `acceptance-gate-report.md`
  - `protocol-phase-trace.csv`
  - `websocket-inference-log.jsonl`
- Report experiment id: `m7-10-1-physical-device-evidence-rerun-20260330T161622Z`
- Source mode: `live`
- Context: `internal_dashboard`
- WS URL: `ws://127.0.0.1:8120/ws/live`
- Health: `ok`, `model_loaded=true`

## Factual Summary

1. Rerun executed with `watch_accelerometer + polar_hr + polar_rr`.
2. Protocol phases remain `rest -> movement -> recovery`.
3. Sent `12` batches and captured `5` inference responses (`error_count=0`).
4. Live canary evidence is present:
   - `activity_canary_present=true`
   - `arousal_canary_present=true`
5. Gate remains blocked because no file was provided to `--real-device-evidence`, therefore:
   - `real_device_evidence_present=false`
   - `device_protocol_validated=false`
   - `gate_decision=blocked`

## Gate Decision

- Decision: `blocked`
- Reason: `No real physical-device evidence was present in this run.`

## Next

`M7.10.2 - Provide concrete physical-device evidence path and rerun gate with --real-device-evidence`
