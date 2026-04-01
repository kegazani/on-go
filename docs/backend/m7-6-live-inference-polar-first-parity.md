# M7.6 Live Inference API Polar-first Online Feature Parity

## Status

- Step ID: `M7.6`
- Status: `completed`
- Date: `2026-03-29`
- Scope: `P6` live websocket parity contract for Polar-first runtime telemetry.

## Goal

Bring `live-inference-api` websocket telemetry to the same Polar-first runtime contract that was frozen in `M7.5`.

The live socket must not only keep serving inference. It must also make feature coverage visible so we can tell whether online extraction is still watch-centric or has actually reached bundle parity.

## Source of Truth

1. `M7.5` runtime bundle export.
2. `model-bundle.manifest.json` in the exported runtime bundle.
3. Per-track feature-name payloads from the bundle export.

Canonical M7.5 bundle shapes:

1. `activity` -> watch motion only.
2. `arousal_coarse` -> Polar-plus-watch motion.
3. `valence_coarse` -> watch motion only.

## Expected Websocket Contract

The `inference` payload should keep the existing semantic fields and add:

1. `feature_count_total`
2. `feature_count_nonzero`
3. `feature_coverage_by_track`

`feature_coverage_by_track` must contain entries for:

1. `activity`
2. `arousal_coarse`
3. `valence_coarse`

Each track entry must expose:

1. `expected_feature_count`
2. `present_feature_count`
3. `nonzero_feature_count`
4. `missing_features`

## Polar-first Arousal Parity Rule

`arousal_coarse` is the parity-sensitive track.

When `polar_hr` is the heart source:

1. the arousal coverage block must include chest-prefixed features from the M7.5 bundle;
2. `chest_ecg_*` must be visible in the telemetry;
3. the response should make the Polar-plus-watch motion split explicit instead of collapsing it into a legacy watch-only feature count.

## Acceptance Smoke

The websocket parity smoke is acceptable when all of the following are true:

1. `source_mode=live` batches with `watch_accelerometer` and `polar_hr` emit an `inference` response.
2. The response includes `feature_count_total`.
3. The response includes `feature_count_nonzero`.
4. The response includes `feature_coverage_by_track`.
5. The arousal track coverage includes `chest_ecg_*`.
6. Existing semantic fields still appear unchanged.

## Failure Modes

1. If only the old `feature_count` is emitted, parity is still incomplete.
2. If `arousal_coarse` remains watch-only, the live API is not aligned with `M7.5`.
3. If the websocket contract hides the track-level split, regression analysis becomes impossible.

## Result

1. `live-inference-api` now emits `feature_count_total`, `feature_count_nonzero`, and `feature_coverage_by_track` on websocket inference.
2. Track coverage reports `expected_feature_count`, `present_feature_count`, `nonzero_feature_count`, and `missing_features`.
3. Polar-first arousal parity is visible in the live payload when `polar_hr` is streamed.
4. Local verification passed: `python3 -m pytest -q tests` in `services/live-inference-api` -> `17 passed`.

## Next

1. `M7.7 - P7 on-go-ios Integration for Polar-first Runtime`.
