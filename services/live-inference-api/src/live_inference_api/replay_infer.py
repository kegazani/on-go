from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from live_inference_api.activity_context_adjust import adjust_activity_label_for_context
from live_inference_api.features import extract_watch_features
from live_inference_api.loader import LoadedBundle, LoadedTrack, predict
from live_inference_api.semantics import build_valence_scoped_status, derive_semantic_state
from live_inference_api.user_display_label import compute_user_display_label


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


ALLOWED_STREAM_NAMES = frozenset(
    {
        "watch_heart_rate",
        "watch_accelerometer",
        "polar_hr",
        "polar_rr",
        "watch_activity_context",
        "watch_hrv",
    }
)


def _required_primary_streams(bundle: LoadedBundle) -> tuple[str, ...]:
    default = ("polar_hr", "watch_accelerometer")
    required = tuple(s for s in bundle.required_live_streams if s in ALLOWED_STREAM_NAMES)
    if required:
        return required
    return default


def _resolve_heart_source(streams_with_samples: set[str]) -> Optional[str]:
    if "polar_hr" in streams_with_samples:
        return "polar_hr"
    if "watch_heart_rate" in streams_with_samples:
        return "watch_heart_rate"
    return None


def _group_samples_by_stream(
    samples: list[dict[str, Any]],
) -> dict[str, list[tuple[int, dict[str, Any]]]]:
    buckets: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for item in samples:
        name = item.get("stream_name")
        if not isinstance(name, str):
            continue
        offset = item.get("offset_ms")
        values = item.get("values")
        if not isinstance(offset, (int, float)) or not isinstance(values, dict):
            continue
        buckets.setdefault(name, []).append((int(offset), values))
    for stream_name in buckets:
        buckets[stream_name].sort(key=lambda x: x[0])
    return buckets


def _values_for_stream(
    grouped: dict[str, list[tuple[int, dict[str, Any]]]],
    stream_name: str,
) -> list[dict[str, Any]]:
    return [v for _, v in sorted(grouped.get(stream_name, []), key=lambda x: x[0])]


def infer_from_replay_window_json(
    *,
    window: dict[str, Any],
    bundle: LoadedBundle,
    context: str,
) -> dict[str, Any]:
    window_start = int(window.get("from_offset_ms", 0))
    window_end = int(window.get("to_offset_ms", 0))
    warnings = window.get("warnings") if isinstance(window.get("warnings"), list) else []
    warnings_out = [str(w) for w in warnings]

    samples_raw = window.get("samples")
    if not isinstance(samples_raw, list):
        samples_raw = []

    grouped = _group_samples_by_stream(samples_raw)
    streams_present = {k for k, v in grouped.items() if v}

    heart_source = _resolve_heart_source(streams_present)
    acc_vals = _values_for_stream(grouped, "watch_accelerometer")
    rr_vals_dicts = _values_for_stream(grouped, "polar_rr")
    act_ctx = _values_for_stream(grouped, "watch_activity_context")

    hr_vals: list[dict[str, Any]] = []
    if heart_source:
        hr_vals = _values_for_stream(grouped, heart_source)

    required = set(_required_primary_streams(bundle))

    if not acc_vals or heart_source is None or not hr_vals:
        return {
            "window_start_ms": window_start,
            "window_end_ms": window_end,
            "skipped": True,
            "skip_reason": "insufficient_streams",
            "detail": {
                "missing_acc": not bool(acc_vals),
                "missing_hr": not bool(hr_vals),
                "heart_source": heart_source,
            },
            "replay_warnings": warnings_out,
        }

    if "polar_rr" in required and not rr_vals_dicts:
        return {
            "window_start_ms": window_start,
            "window_end_ms": window_end,
            "skipped": True,
            "skip_reason": "missing_required_streams",
            "detail": {"missing_required_streams": ["polar_rr"]},
            "replay_warnings": warnings_out,
        }

    sample_count = sum(len(grouped.get(n, ())) for n in grouped)
    features = extract_watch_features(
        acc_vals,
        hr_vals,
        rr_vals_dicts,
        (window_end - window_start) / 1000.0,
        sample_count,
        heart_source=heart_source,
        manifest_layout=bundle.uses_manifest,
        activity_context_samples=act_ctx if act_ctx else None,
    )
    pred = predict(bundle, features)
    activity_for_semantics = adjust_activity_label_for_context(
        str(pred.get("activity", "")),
        act_ctx if act_ctx else None,
    )
    valence_scoped_status = build_valence_scoped_status(
        context=context,
        has_valence_model=bundle.valence_coarse is not None,
    )
    feature_names = _bundle_feature_names(bundle)
    feature_count_nonzero = sum(1 for name in feature_names if features.get(name, 0.0) != 0.0)
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
    return {
        "window_start_ms": window_start,
        "window_end_ms": window_end,
        "skipped": False,
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
            "activity": _track_feature_coverage(bundle.activity, features),
            "arousal_coarse": _track_feature_coverage(bundle.arousal_coarse, features),
            **(
                {"valence_coarse": _track_feature_coverage(bundle.valence_coarse, features)}
                if bundle.valence_coarse is not None
                else {}
            ),
        },
        "feature_count": feature_count_legacy,
        "replay_warnings": warnings_out,
    }


def _parse_manifest_streams(manifest: dict[str, Any]) -> list[str]:
    streams = manifest.get("streams")
    if not isinstance(streams, list):
        return []
    out: list[str] = []
    for row in streams:
        if not isinstance(row, dict):
            continue
        name = row.get("stream_name")
        if isinstance(name, str) and name in ALLOWED_STREAM_NAMES:
            if row.get("available_for_replay", False):
                out.append(name)
    return sorted(set(out))


def resolve_stream_names_for_infer(
    *,
    manifest: dict[str, Any],
    bundle: LoadedBundle,
    requested: Optional[list[str]],
) -> list[str]:
    available = _parse_manifest_streams(manifest)
    if not available:
        return []
    required = set(_required_primary_streams(bundle))
    if requested:
        unknown = set(requested) - ALLOWED_STREAM_NAMES
        if unknown:
            raise ValueError(f"unknown stream names: {sorted(unknown)}")
        names = [n for n in requested if n in available]
        if not names:
            names = list(available)
    else:
        names = list(available)
    for r in required:
        if r in available and r not in names:
            names.append(r)
    seen: set[str] = set()
    ordered: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


async def fetch_replay_json(client: httpx.AsyncClient, method: str, url: str, json_body: Any = None) -> tuple[int, Any]:
    try:
        if method.upper() == "GET":
            r = await client.get(url)
        else:
            r = await client.post(url, json=json_body)
    except httpx.RequestError as e:
        raise RuntimeError(f"replay_transport_error: {e}") from e
    try:
        body = r.json()
    except json.JSONDecodeError:
        body = {"raw": r.text}
    return r.status_code, body


async def run_replay_infer(
    *,
    base_url: str,
    session_id: str,
    window_ms: int,
    step_ms: int,
    stream_names: Optional[list[str]],
    context: str,
    bundle: LoadedBundle,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    manifest_url = f"{base}/v1/replay/sessions/{session_id}/manifest"
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    try:
        try:
            status, manifest = await fetch_replay_json(client, "GET", manifest_url)
        except RuntimeError as e:
            return {"error": {"http_status": 502, "body": {"message": str(e)}}}
        if status == 404:
            return {"error": {"http_status": 404, "body": manifest}}
        if status == 409:
            return {"error": {"http_status": 409, "body": manifest}}
        if status >= 400:
            return {"error": {"http_status": status, "body": manifest}}

        if not isinstance(manifest, dict):
            return {"error": {"http_status": 502, "body": {"message": "invalid manifest json"}}}

        duration_ms = int(manifest.get("duration_ms", 0))
        try:
            names = resolve_stream_names_for_infer(manifest=manifest, bundle=bundle, requested=stream_names)
        except ValueError as e:
            return {"error": {"http_status": 422, "body": {"message": str(e)}}}

        if not names:
            return {"error": {"http_status": 400, "body": {"message": "no replayable streams in manifest"}}}

        windows_out: list[dict[str, Any]] = []
        from_offset = 0
        if duration_ms <= 0:
            return {"session_id": session_id, "duration_ms": duration_ms, "windows": [], "stream_names": names}

        safe_window = max(100, min(window_ms, duration_ms))

        while from_offset < duration_ms:
            body = {
                "mode": "accelerated",
                "speed_multiplier": 1.0,
                "from_offset_ms": from_offset,
                "window_ms": safe_window,
                "stream_names": names,
                "include_events": False,
                "max_samples_per_stream": 100000,
            }
            wurl = f"{base}/v1/replay/sessions/{session_id}/windows"
            try:
                wstatus, wbody = await fetch_replay_json(client, "POST", wurl, body)
            except RuntimeError as e:
                return {"error": {"http_status": 502, "body": {"message": str(e)}, "from_offset_ms": from_offset}}
            if wstatus >= 400:
                return {"error": {"http_status": wstatus, "body": wbody, "from_offset_ms": from_offset}}
            if not isinstance(wbody, dict):
                return {"error": {"http_status": 502, "body": {"message": "invalid window json"}}}

            row = infer_from_replay_window_json(window=wbody, bundle=bundle, context=context)
            windows_out.append(row)

            from_offset = from_offset + step_ms

        return {
            "session_id": session_id,
            "duration_ms": duration_ms,
            "stream_names": names,
            "window_ms": safe_window,
            "step_ms": step_ms,
            "windows": windows_out,
        }
    finally:
        if own_client and client is not None:
            await client.aclose()
