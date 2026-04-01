# M7.7 on-go-ios Polar-first Runtime Integration

## Status

- Step ID: `M7.7`
- Status: `completed`
- Date: `2026-03-29`
- Scope: `P7` on-go-ios integration for the Polar-first runtime and websocket telemetry contract.

## Goal

Document the iOS-side integration contract for the Polar-first runtime so the app can consume the `M7.6` websocket response with concrete UI/runtime wiring.

The objective is not to redesign the transport. The objective is to make the runtime contract explicit enough that the iPhone UI can show:

1. the live `activity/arousal/valence` outputs;
2. heart-source fallback state;
3. feature-coverage health for long-running physical-device sessions.

## Source of Truth

1. `docs/backend/m7-6-live-inference-polar-first-parity.md`
2. `services/live-inference-api/README.md`
3. `docs/backend/polar-first-feature-contract.md`
4. `docs/backend/polar-first-model-implementation-plan.md`
5. `on-go-ios/docs/live-streaming-changes.md`

## Websocket Fields Consumed by iOS

The iOS app consumes the following websocket fields from `type == "inference"` messages.

| Field | iOS usage |
| --- | --- |
| `activity` | Primary live label shown in the dashboard. |
| `arousal_coarse` | Primary live label shown in the dashboard. |
| `valence_coarse` | Secondary label shown in the dashboard; may be `unknown` or policy-scoped. |
| `derived_state` | Optional semantic summary for QA/debug copy. |
| `confidence.score` | Confidence display and internal sanity signal. |
| `confidence.band` | Confidence badge (`low` / `medium` / `high`). |
| `fallback_reason` | Explains degraded or guarded semantic output. |
| `claim_level` | Distinguishes safe vs guarded interpretation. |
| `heart_source` | Indicates whether the runtime is using `polar_hr` or a fallback heart stream. |
| `heart_source_fallback_active` | Explicit fallback flag for the UI quality banner. |
| `feature_count_total` | Aggregate coverage counter shown in telemetry. |
| `feature_count_nonzero` | Aggregate coverage counter shown in telemetry. |
| `feature_coverage_by_track.activity` | Per-track coverage details for the `activity` model. |
| `feature_coverage_by_track.arousal_coarse` | Per-track coverage details for the `arousal_coarse` model. |
| `feature_coverage_by_track.valence_coarse` | Per-track coverage details for the `valence_coarse` model. |
| `valence_scoped_status.reason` | Stable UI text when valence is blocked by context or model availability. |

Each track coverage block must expose:

1. `expected_feature_count`
2. `present_feature_count`
3. `nonzero_feature_count`
4. `missing_features`

The legacy `feature_count` field can remain for compatibility, but M7.7 should treat the new telemetry block as the canonical contract.

## UI Quality Signals

The runtime should surface two quality signals in the iPhone UI.

### Heart Source Fallback

Treat the heart source as a first-class quality signal.

Recommended presentation:

1. show a green or neutral badge when `heart_source == "polar_hr"` and `heart_source_fallback_active == false`;
2. show an amber badge when `heart_source_fallback_active == true`;
3. show the fallback source explicitly when `heart_source == "watch_heart_rate"`;
4. clear the warning when Polar recovers and the runtime returns to `polar_hr`.

Operational meaning:

1. a fallback is acceptable for resilience during a session;
2. a persistent fallback means the Polar path is degraded and the claim should be treated cautiously;
3. the UI must not silently hide the fallback condition.

### Coverage Counters

Coverage counters are the second quality signal.

Recommended presentation:

1. show `feature_count_nonzero / feature_count_total` as a compact overall health indicator;
2. show per-track coverage when QA/debug mode is enabled;
3. raise a degraded-state banner when any track reports missing features or when the non-zero count collapses to zero;
4. keep the UI readable when `valence_coarse` is unavailable by showing the scoped reason instead of a blank state.

## Integration Checklist

Use this checklist for a physical-device session on the Polar-first runtime.

1. Confirm `live-inference-api` is running and the model bundle is loaded.
2. Set `ON_GO_LIVE_INFERENCE_WS_URL` for the iPhone scheme to the live websocket endpoint.
3. Keep `ON_GO_LIVE_INFERENCE_CONTEXT` aligned with the intended QA scope (`research_only` by default).
4. Start a real iPhone + Apple Watch session with Polar H10 connected.
5. Verify that watch and Polar stream batches are forwarded with `source_mode=live`.
6. Confirm the iPhone dashboard receives `inference` messages and renders `activity`, `arousal`, and `valence`.
7. Confirm the dashboard also shows the quality signals:
   - heart source;
   - fallback state;
   - coverage counters.
8. If Polar is temporarily unavailable, verify that the runtime falls back to `watch_heart_rate` and the UI exposes the fallback state.
9. Restore Polar and confirm the UI clears the fallback state.
10. Keep the session running for at least 10 minutes with changing states (`rest -> movement -> recovery` or equivalent protocol transitions).
11. Stop the session cleanly and confirm the websocket disconnects without stale UI state.

## Acceptance Criteria for a 10+ Minute Session

The step is acceptable when all of the following are true on a real device pair.

1. The session remains stable for at least 10 minutes.
2. The websocket stays connected for the full session.
3. At least one `inference` window is emitted during the session.
4. The app displays `activity`, `arousal_coarse`, and `valence_coarse` values during recording.
5. The payload includes `feature_count_total`, `feature_count_nonzero`, and `feature_coverage_by_track`.
6. The payload includes `heart_source` and `heart_source_fallback_active`.
7. If a fallback occurs, it becomes visible in the UI and later clears when Polar recovers.
8. Per-track coverage blocks contain `expected_feature_count`, `present_feature_count`, `nonzero_feature_count`, and `missing_features`.
9. The session demonstrates changing states under the protocol, not a static one-window capture.
10. The app stops cleanly and does not retain stale inference values after disconnect.

## Troubleshooting

1. If no inference appears, check that the websocket URL uses `ws://` or `wss://` and that the backend reports `model_loaded=true`.
2. If the backend rejects batches, check that every forwarded batch has `source_mode=live`.
3. If the UI shows `model_not_loaded`, the bundle path or manifest is wrong.
4. If the UI shows `blocked_by_context`, the runtime context is not allowed for valence in that session.
5. If `heart_source_fallback_active` never clears, check Polar proximity, device connectivity, and the heart-stream path.
6. If coverage counters stay at zero, treat it as a manifest or feature-space mismatch until proven otherwise.
7. If `feature_coverage_by_track.arousal_coarse.missing_features` is non-empty, do not treat the session as claim-clean.

## Result

1. The iOS-facing Polar-first runtime contract is documented explicitly.
2. The telemetry contract now includes both semantic outputs and quality signals.
3. The 10+ minute session acceptance bar is written down for P7 validation.

## Next

1. `M7.8 - P8 Acceptance and Claim Gate`.
