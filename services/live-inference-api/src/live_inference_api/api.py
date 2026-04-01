from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from live_inference_api.activity_context_adjust import adjust_activity_label_for_context
from live_inference_api.buffer import StreamBuffer
from live_inference_api.config import Settings
from live_inference_api.features import extract_watch_features
from live_inference_api.loader import LoadedBundle, LoadedTrack, load_model_bundle, predict
from live_inference_api.replay_infer import run_replay_infer
from live_inference_api.semantics import build_valence_scoped_status, derive_semantic_state
from live_inference_api.user_display_label import compute_user_display_label

logger = logging.getLogger(__name__)

model_bundle: LoadedBundle | None = None
ALLOWED_STREAM_NAMES = {
    "watch_heart_rate",
    "watch_accelerometer",
    "polar_hr",
    "polar_rr",
    "watch_activity_context",
    "watch_hrv",
}
ALLOWED_SOURCE_MODES = {"live"}
DEFAULT_REQUIRED_PRIMARY_STREAMS = ("polar_hr", "watch_accelerometer")


class ReplayInferRequestBody(BaseModel):
    session_id: str = Field(min_length=1)
    window_ms: int | None = Field(default=None, ge=100, le=600000)
    step_ms: int | None = Field(default=None, ge=100, le=600000)
    stream_names: list[str] | None = None
    context: str = "public_app"
    replay_base_url: str | None = None


async def _send_error(websocket: WebSocket, code: str, detail: str) -> None:
    await websocket.send_json({"type": "error", "code": code, "detail": detail})


def _normalize_source_mode(msg: dict[str, object]) -> str | None:
    source_mode = msg.get("source_mode")
    if source_mode is None:
        return None
    normalized = str(source_mode).strip().lower()
    return normalized or None


def _bundle_feature_names(bundle: LoadedBundle) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for track in (bundle.activity, bundle.arousal_coarse, bundle.valence_coarse):
        if track is None:
            continue
        for feature_name in track.feature_names:
            if feature_name not in seen:
                seen.add(feature_name)
                names.append(feature_name)
    return names


_PREDICTION_LOG_KEYS = (
    "activity",
    "activity_class",
    "arousal_coarse",
    "valence_coarse",
    "user_display_label",
    "valence_scoped_status",
    "derived_state",
    "confidence",
    "fallback_reason",
    "claim_level",
    "heart_source",
    "heart_source_fallback_active",
    "feature_count_total",
    "feature_count_nonzero",
)


def _slice_prediction_for_log(response: dict[str, object]) -> dict[str, object]:
    return {k: response[k] for k in _PREDICTION_LOG_KEYS if k in response}


def _prediction_fields_delta(
    previous: dict[str, object] | None,
    current: dict[str, object],
) -> dict[str, object]:
    if previous is None:
        return dict(current)
    return {k: v for k, v in current.items() if previous.get(k) != v}


def _track_feature_coverage(track: LoadedTrack, feature_vector: dict[str, float]) -> dict[str, object]:
    expected = track.feature_names
    present_feature_count = sum(1 for name in expected if name in feature_vector)
    nonzero_feature_count = sum(1 for name in expected if feature_vector.get(name, 0.0) != 0.0)
    missing_features = [name for name in expected if name not in feature_vector][:10]
    return {
        "expected_feature_count": len(expected),
        "present_feature_count": present_feature_count,
        "nonzero_feature_count": nonzero_feature_count,
        "missing_features": missing_features,
    }


def _required_primary_streams(bundle: LoadedBundle | None) -> tuple[str, ...]:
    if bundle is None:
        return DEFAULT_REQUIRED_PRIMARY_STREAMS
    required = tuple(stream for stream in bundle.required_live_streams if stream in ALLOWED_STREAM_NAMES)
    if required:
        return required
    return DEFAULT_REQUIRED_PRIMARY_STREAMS


def create_app(settings: Settings | None = None) -> FastAPI:
    global model_bundle
    cfg = settings or Settings.from_env()
    app = FastAPI(
        title="On-Go Live Inference API",
        version="0.1.0",
        description="WebSocket API for real-time streaming inference from sensor samples.",
    )

    if cfg.model_dir and cfg.model_dir.exists():
        try:
            model_bundle = load_model_bundle(cfg.model_dir)
        except Exception as e:
            logger.warning("model bundle not loaded: %s", e)

    @app.get("/health")
    async def health() -> dict[str, str]:
        loaded = model_bundle is not None
        return {"status": "ok", "model_loaded": str(loaded).lower()}

    async def _replay_infer_handler(req: ReplayInferRequestBody):
        if model_bundle is None:
            raise HTTPException(status_code=503, detail="model bundle not loaded")
        base = (req.replay_base_url or cfg.replay_service_base_url).strip()
        result = await run_replay_infer(
            base_url=base,
            session_id=req.session_id.strip(),
            window_ms=req.window_ms if req.window_ms is not None else cfg.window_size_ms,
            step_ms=req.step_ms if req.step_ms is not None else cfg.step_size_ms,
            stream_names=req.stream_names,
            context=req.context,
            bundle=model_bundle,
        )
        if "error" in result:
            err = result["error"]
            return JSONResponse(status_code=int(err["http_status"]), content=result)
        return result

    @app.post("/v1/replay/infer")
    async def replay_infer(req: ReplayInferRequestBody):
        return await _replay_infer_handler(req)

    @app.post("/api/v1/replay/infer")
    async def replay_infer_api_prefix(req: ReplayInferRequestBody):
        return await _replay_infer_handler(req)

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket) -> None:
        await websocket.accept()
        buffer = StreamBuffer(
            window_size_ms=cfg.window_size_ms,
            step_size_ms=cfg.step_size_ms,
            max_heart_staleness_ms=cfg.heart_staleness_ms,
        )
        context = "public_app"
        last_heart_source: str | None = None
        last_prediction_snapshot: dict[str, object] | None = None
        seen_streams: set[str] = set()
        primary_policy_fallback_notified = False
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await _send_error(websocket, "invalid_json", "invalid json")
                    continue
                msg_type = msg.get("type", "")
                if msg_type == "stream_batch":
                    stream_name = msg.get("stream_name") or msg.get("stream")
                    if not stream_name or stream_name not in ALLOWED_STREAM_NAMES:
                        await _send_error(websocket, "invalid_stream_name", "unknown stream")
                        continue
                    source_mode = _normalize_source_mode(msg)
                    if source_mode not in ALLOWED_SOURCE_MODES:
                        rendered_source_mode = source_mode or "missing"
                        await _send_error(
                            websocket,
                            "live_source_required",
                            f"stream_batch requires source_mode=live; got {rendered_source_mode}",
                        )
                        continue
                    if isinstance(msg.get("context"), str) and msg.get("context"):
                        context = str(msg.get("context"))
                    seen_streams.add(stream_name)
                    samples = msg.get("samples", [])
                    logger.info(
                        "stream_batch received stream=%s samples=%s source_mode=%s context=%s",
                        stream_name,
                        len(samples) if isinstance(samples, list) else "invalid",
                        source_mode,
                        context,
                    )
                    for s in samples:
                        offset = s.get("offset_ms", s.get("offset"))
                        vals = s.get("values", s)
                        if isinstance(offset, (int, float)) and isinstance(vals, dict):
                            buffer.add(stream_name, int(offset), vals)
                    result = buffer.try_emit_window()
                    if result and model_bundle is not None:
                        window_start, window_end, heart_source, acc_w, hr_w, rr_w, act_ctx_w = result
                        required_primary_streams = _required_primary_streams(model_bundle)
                        missing_primary_streams = [
                            stream for stream in required_primary_streams if stream not in seen_streams
                        ]
                        if missing_primary_streams:
                            if not primary_policy_fallback_notified:
                                logger.warning(
                                    "polar_primary_policy fallback active; missing streams: %s",
                                    ",".join(missing_primary_streams),
                                )
                                await _send_error(
                                    websocket,
                                    "polar_primary_policy_fallback",
                                    "missing required primary streams: "
                                    + ",".join(missing_primary_streams)
                                    + "; using fallback heart source policy",
                                )
                                primary_policy_fallback_notified = True
                        if heart_source != last_heart_source:
                            if heart_source == "watch_heart_rate":
                                logger.warning("polar_hr unavailable, fallback to watch_heart_rate")
                                await _send_error(
                                    websocket,
                                    "heart_source_fallback_active",
                                    "polar_hr unavailable; using watch_heart_rate as fallback heart source",
                                )
                            elif heart_source == "polar_hr" and last_heart_source == "watch_heart_rate":
                                logger.info("polar_hr recovered, fallback disabled")
                                await _send_error(
                                    websocket,
                                    "heart_source_recovered",
                                    "polar_hr recovered; heart source switched back from watch_heart_rate",
                                )
                            last_heart_source = heart_source
                        acc_vals = [v for _, v in acc_w]
                        hr_vals = [v for _, v in hr_w]
                        features = extract_watch_features(
                            acc_vals,
                            hr_vals,
                            [v for _, v in rr_w],
                            (window_end - window_start) / 1000.0,
                            len(acc_w) + len(hr_w) + len(rr_w),
                            heart_source=heart_source,
                            manifest_layout=model_bundle.uses_manifest,
                            activity_context_samples=[v for _, v in act_ctx_w],
                        )
                        pred = predict(model_bundle, features)
                        act_ctx_vals = [v for _, v in act_ctx_w]
                        activity_for_semantics = adjust_activity_label_for_context(
                            str(pred.get("activity", "")),
                            act_ctx_vals,
                        )
                        valence_scoped_status = build_valence_scoped_status(
                            context=context,
                            has_valence_model=model_bundle.valence_coarse is not None,
                        )
                        feature_names = _bundle_feature_names(model_bundle)
                        feature_count_nonzero = sum(
                            1 for name in feature_names if features.get(name, 0.0) != 0.0
                        )
                        feature_count_legacy = sum(1 for value in features.values() if value != 0.0)
                        semantic = derive_semantic_state(
                            activity_label=activity_for_semantics,
                            arousal_label=str(pred.get("arousal_coarse", "")),
                            valence_label=str(pred.get("valence_coarse", "")),
                            valence_status=valence_scoped_status,
                        )
                        user_display_label = compute_user_display_label(
                            activity_class=str(semantic["activity_class"]),
                            arousal_coarse=str(semantic["arousal_coarse"]),
                            valence_coarse=str(semantic["valence_coarse"]),
                            derived_state=str(semantic["derived_state"]),
                        )
                        response = {
                            "type": "inference",
                            "window_start_ms": window_start,
                            "window_end_ms": window_end,
                            "activity": activity_for_semantics,
                            "activity_class": semantic["activity_class"],
                            "arousal_coarse": semantic["arousal_coarse"],
                            "valence_coarse": semantic["valence_coarse"],
                            "user_display_label": user_display_label,
                            "valence_scoped_status": valence_scoped_status,
                            "derived_state": semantic["derived_state"],
                            "confidence": semantic["confidence"],
                            "fallback_reason": semantic["fallback_reason"],
                            "claim_level": semantic["claim_level"],
                            "heart_source": heart_source,
                            "heart_source_fallback_active": heart_source != "polar_hr",
                            "feature_count_total": len(feature_names),
                            "feature_count_nonzero": feature_count_nonzero,
                            "feature_coverage_by_track": {
                                "activity": _track_feature_coverage(model_bundle.activity, features),
                                "arousal_coarse": _track_feature_coverage(model_bundle.arousal_coarse, features),
                                **(
                                    {"valence_coarse": _track_feature_coverage(model_bundle.valence_coarse, features)}
                                    if model_bundle.valence_coarse is not None
                                    else {}
                                ),
                            },
                            "feature_count": feature_count_legacy,
                        }
                        pred_slice = _slice_prediction_for_log(response)
                        pred_delta = _prediction_fields_delta(last_prediction_snapshot, pred_slice)
                        last_prediction_snapshot = pred_slice
                        logger.info(
                            "inference outbound window=%s-%s prediction_new_or_changed=%s prediction=%s",
                            window_start,
                            window_end,
                            json.dumps(pred_delta, default=str),
                            json.dumps(pred_slice, default=str),
                        )
                        await websocket.send_json(response)
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("websocket error")
            try:
                await _send_error(websocket, "internal_error", str(e))
            except Exception:
                pass

    return app
