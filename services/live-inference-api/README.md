# live-inference-api

WebSocket API for real-time streaming inference. Client sends sensor samples, server returns direct outputs and semantic derived-state fields.

This socket is live-capture only: `source_mode=live` is required on every `stream_batch`.
`simulated`, `unknown`, and replay-origin batches are rejected at runtime.

## Endpoints

- `GET /health` — health check, `model_loaded` indicates if model is ready
- `WS /ws/live` — WebSocket for streaming samples and receiving inference

## WebSocket protocol

### Client -> Server

**stream_batch** — sample batch for a stream:
```json
{
  "type": "stream_batch",
  "stream_name": "polar_hr",
  "source_mode": "live",
  "context": "internal_dashboard",
  "samples": [
    {"offset_ms": 0, "values": {"hr_bpm": 72}},
    {"offset_ms": 1000, "values": {"hr_bpm": 74}}
  ]
}
```

Supported `stream_name`:
- `watch_accelerometer`
- `polar_hr` (preferred heart stream)
- `watch_heart_rate` (fallback heart stream)
- `polar_rr`
- `watch_activity_context`
- `watch_hrv`

Inference window currently requires `watch_accelerometer` and one heart stream (`polar_hr` preferred, `watch_heart_rate` fallback).
`source_mode` is required; only `live` passes the gate. `context` (optional) influences scoped valence policy in the semantic response and does not authorize the batch.

## M7.6 telemetry parity target

`M7.6` keeps the websocket inference shape but adds explicit feature telemetry so the live path can be compared against the `M7.5` runtime bundle:

- `feature_count_total` - total unique feature slots resolved from the manifest-backed track bundle
- `feature_count_nonzero` - total non-zero features across those track-specific spaces
- `feature_coverage_by_track` - per-track coverage block with:
  - `expected_feature_count`
  - `present_feature_count`
  - `nonzero_feature_count`
  - `missing_features`

Polar-first arousal parity is the main gate:

- when `polar_hr` is streamed, the `arousal_coarse` coverage block must expose chest-prefixed features from the bundle, especially `chest_ecg_*`
- `watch_acc_*` stays part of the arousal track because the runtime bundle is Polar-plus-watch motion, not chest-only
- the telemetry should make missing parity explicit instead of collapsing everything into the legacy `feature_count`

**ping**:
```json
{"type": "ping"}
```

### Server -> Client

**inference** — prediction for a completed window (K5.2 semantic shape):
```json
{
  "type": "inference",
  "window_start_ms": 0,
  "window_end_ms": 15000,
  "activity": "baseline",
  "activity_class": "rest",
  "arousal_coarse": "low",
  "valence_coarse": "unknown",
  "valence_scoped_status": {
    "mode": "internal_scoped",
    "context": "internal_dashboard",
    "enabled_for_context": true,
    "user_facing_claims": false,
    "risk_notifications": true,
    "auto_personalization_trigger": false,
    "reason": "valence_model_not_available"
  },
  "derived_state": "calm_rest",
  "confidence": {
    "score": 0.82,
    "band": "high"
  },
  "fallback_reason": "none",
  "claim_level": "safe",
  "heart_source": "polar_hr",
  "heart_source_fallback_active": false,
  "feature_count": 17,
  "feature_count_total": 25,
  "feature_count_nonzero": 17,
  "feature_coverage_by_track": {
    "activity": {
      "expected_feature_count": 20,
      "present_feature_count": 20,
      "nonzero_feature_count": 12,
      "missing_features": []
    },
    "arousal_coarse": {
      "expected_feature_count": 25,
      "present_feature_count": 25,
      "nonzero_feature_count": 17,
      "missing_features": []
    },
    "valence_coarse": {
      "expected_feature_count": 20,
      "present_feature_count": 20,
      "nonzero_feature_count": 12,
      "missing_features": []
    }
  }
}
```

**pong**: `{"type": "pong"}`

**error**: `{"type": "error", "code": "...", "detail": "..."}`

When `polar_hr` is unavailable and runtime switches to watch fallback, server sends:
- `code=heart_source_fallback_active`

When `polar_hr` comes back and fallback is disabled, server sends:
- `code=heart_source_recovered`

## Config (env)

- `LIVE_INFERENCE_APP_HOST` (default: 0.0.0.0)
- `LIVE_INFERENCE_APP_PORT` (default: 8120)
- `LIVE_INFERENCE_MODEL_DIR` or `INFERENCE_MODEL_DIR` — model bundle path
- `LIVE_INFERENCE_WINDOW_MS` (default: 15000) — window size
- `LIVE_INFERENCE_STEP_MS` (default: 5000) — step between windows

## Model

Канонический runtime-format общий с `inference-api`:

- `model-bundle.manifest.json`
- per-track `*.joblib`
- per-track `*_feature_names.json`

Manifest позволяет держать разные feature spaces для:

- `activity`
- `arousal_coarse`
- optional `valence_coarse`

Legacy fallback на `watch_only_centroid_* + feature_names.json` пока сохранен только для совместимости.

Текущий live feature adapter все еще строит watch-style online features:

- `watch_accelerometer` -> `watch_acc_*`
- heart stream (`polar_hr` или `watch_heart_rate`) -> `watch_bvp_*`

Missing `watch_eda_*`, `watch_temp_*` filled with `0`. Это значит, что manifest-driven loader уже готов к mixed per-track bundles, но live raw-stream contract еще не доведен до полного `Polar + Watch fusion` path.

Replay- и simulated-источники сюда не подаются. Для сохраненных raw sessions используй `replay-service`.

## Local run

```
cd services/live-inference-api
LIVE_INFERENCE_MODEL_DIR=/path/to/models live-inference-api
```

## Docker

Port 8120. Mount model directory to `/models`.
