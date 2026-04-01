from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from live_inference_api import api
from live_inference_api.api import create_app
from live_inference_api.config import Settings
from live_inference_api.loader import load_model_bundle
from live_inference_api.features import extract_watch_features

M7_5_RUNTIME_BUNDLE_DIR = Path(
    "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-5-runtime-bundle-export"
)


def _open_client() -> TestClient:
    return TestClient(create_app(Settings()))


def _build_bundle() -> object:
    return load_model_bundle(M7_5_RUNTIME_BUNDLE_DIR)


def _bundle_feature_names(bundle: object) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for track in (bundle.activity, bundle.arousal_coarse, bundle.valence_coarse):
        if track is None:
            continue
        for name in track.feature_names:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _expected_feature_telemetry(features: dict[str, float], bundle: object) -> dict[str, object]:
    activity_names = bundle.activity.feature_names
    arousal_names = bundle.arousal_coarse.feature_names
    valence_names = bundle.valence_coarse.feature_names
    feature_names = _bundle_feature_names(bundle)
    return {
        "feature_count_total": len(feature_names),
        "feature_count_nonzero": sum(1 for name in feature_names if features.get(name, 0.0) != 0.0),
        "feature_coverage_by_track": {
            "activity": {
                "expected_feature_count": len(activity_names),
                "present_feature_count": sum(1 for name in activity_names if name in features),
                "nonzero_feature_count": sum(1 for name in activity_names if features.get(name, 0.0) != 0.0),
                "missing_features": [name for name in activity_names if name not in features][:10],
            },
            "arousal_coarse": {
                "expected_feature_count": len(arousal_names),
                "present_feature_count": sum(1 for name in arousal_names if name in features),
                "nonzero_feature_count": sum(1 for name in arousal_names if features.get(name, 0.0) != 0.0),
                "missing_features": [name for name in arousal_names if name not in features][:10],
            },
            "valence_coarse": {
                "expected_feature_count": len(valence_names),
                "present_feature_count": sum(1 for name in valence_names if name in features),
                "nonzero_feature_count": sum(1 for name in valence_names if features.get(name, 0.0) != 0.0),
                "missing_features": [name for name in valence_names if name not in features][:10],
            },
        },
    }


def test_live_stream_batch_accepts_only_live_source_mode(monkeypatch) -> None:
    add_calls: list[tuple[str, int, dict[str, object]]] = []

    monkeypatch.setattr(api, "model_bundle", _build_bundle())
    monkeypatch.setattr(
        api.StreamBuffer,
        "add",
        lambda self, stream_name, offset_ms, values: add_calls.append((stream_name, offset_ms, values)),
    )
    def emit_only_after_required_streams(_self):
        seen = {name for name, *_ in add_calls}
        if not {"watch_accelerometer", "polar_hr"}.issubset(seen):
            return None
        return (
            0,
            15000,
            "polar_hr",
            [(0, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})],
            [(0, {"hr_bpm": 72})],
            [],
            [],
        )

    monkeypatch.setattr(api.StreamBuffer, "try_emit_window", emit_only_after_required_streams)
    monkeypatch.setattr(
        api,
        "predict",
        lambda bundle, features: {
            "activity": "baseline",
            "arousal_coarse": "low",
            "valence_coarse": "unknown",
        },
    )

    with _open_client() as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json(
                {
                    "type": "stream_batch",
                    "source_mode": "live",
                    "stream_name": "watch_accelerometer",
                    "context": "internal_dashboard",
                    "samples": [
                        {"offset_ms": 0, "values": {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}},
                    ],
                }
            )
            ws.send_json(
                {
                    "type": "stream_batch",
                    "source_mode": "live",
                    "stream_name": "polar_hr",
                    "context": "internal_dashboard",
                    "samples": [
                        {"offset_ms": 0, "values": {"hr_bpm": 72}},
                        {"offset_ms": 1000, "values": {"hr_bpm": 74}},
                    ],
                }
            )
            payload = ws.receive_json()

    assert add_calls == [
        ("watch_accelerometer", 0, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}),
        ("polar_hr", 0, {"hr_bpm": 72}),
        ("polar_hr", 1000, {"hr_bpm": 74}),
    ]
    assert payload["type"] == "inference"
    assert payload["heart_source"] == "polar_hr"
    assert payload["heart_source_fallback_active"] is False
    assert payload["window_start_ms"] == 0
    assert payload["window_end_ms"] == 15000


def test_live_stream_batch_emits_feature_telemetry_contract(monkeypatch) -> None:
    bundle = _build_bundle()
    add_calls: list[tuple[str, int, dict[str, object]]] = []

    monkeypatch.setattr(api, "model_bundle", bundle)
    monkeypatch.setattr(
        api.StreamBuffer,
        "add",
        lambda self, stream_name, offset_ms, values: add_calls.append((stream_name, offset_ms, values)),
    )

    def emit_only_after_required_streams(_self):
        seen = {name for name, *_ in add_calls}
        if not {"watch_accelerometer", "polar_hr"}.issubset(seen):
            return None
        return (
            0,
            15000,
            "polar_hr",
            [(0, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})],
            [(0, {"hr_bpm": 72}), (1000, {"hr_bpm": 74})],
            [],
            [],
        )

    monkeypatch.setattr(api.StreamBuffer, "try_emit_window", emit_only_after_required_streams)
    monkeypatch.setattr(
        api,
        "predict",
        lambda bundle, features: {
            "activity": "baseline",
            "arousal_coarse": "low",
            "valence_coarse": "unknown",
        },
    )

    acc_samples = [{"offset_ms": 0, "values": {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}}]
    hr_samples = [
        {"offset_ms": 0, "values": {"hr_bpm": 72}},
        {"offset_ms": 1000, "values": {"hr_bpm": 74}},
    ]
    features = extract_watch_features(
        [sample["values"] for sample in acc_samples],
        [sample["values"] for sample in hr_samples],
        [],
        15.0,
        len(acc_samples) + len(hr_samples),
        heart_source="polar_hr",
        manifest_layout=True,
    )
    expected = _expected_feature_telemetry(features, bundle)

    with _open_client() as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json(
                {
                    "type": "stream_batch",
                    "source_mode": "live",
                    "stream_name": "watch_accelerometer",
                    "context": "internal_dashboard",
                    "samples": acc_samples,
                }
            )
            ws.send_json(
                {
                    "type": "stream_batch",
                    "source_mode": "live",
                    "stream_name": "polar_hr",
                    "context": "internal_dashboard",
                    "samples": hr_samples,
                }
            )
            payload = ws.receive_json()

    assert add_calls == [
        ("watch_accelerometer", 0, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}),
        ("polar_hr", 0, {"hr_bpm": 72}),
        ("polar_hr", 1000, {"hr_bpm": 74}),
    ]
    assert payload["type"] == "inference"
    assert payload["heart_source"] == "polar_hr"
    assert payload["heart_source_fallback_active"] is False
    assert payload["feature_count_total"] == expected["feature_count_total"]
    assert payload["feature_count_nonzero"] == expected["feature_count_nonzero"]
    assert payload["feature_coverage_by_track"] == expected["feature_coverage_by_track"]
    assert payload["feature_coverage_by_track"]["arousal_coarse"]["present_feature_count"] == 25
    assert payload["feature_coverage_by_track"]["arousal_coarse"]["nonzero_feature_count"] == 17
    assert payload["feature_coverage_by_track"]["arousal_coarse"]["missing_features"] == []


def test_live_stream_batch_emits_fallback_error_when_using_watch_hr(monkeypatch) -> None:
    add_calls: list[tuple[str, int, dict[str, object]]] = []

    monkeypatch.setattr(api, "model_bundle", _build_bundle())
    monkeypatch.setattr(
        api.StreamBuffer,
        "add",
        lambda self, stream_name, offset_ms, values: add_calls.append((stream_name, offset_ms, values)),
    )
    monkeypatch.setattr(
        api.StreamBuffer,
        "try_emit_window",
        lambda self: (
            0,
            15000,
            "watch_heart_rate",
            [(0, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})],
            [(0, {"hr_bpm": 72})],
            [],
            [],
        ),
    )
    monkeypatch.setattr(
        api,
        "predict",
        lambda bundle, features: {
            "activity": "baseline",
            "arousal_coarse": "low",
            "valence_coarse": "unknown",
        },
    )

    with _open_client() as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json(
                {
                    "type": "stream_batch",
                    "source_mode": "live",
                    "stream_name": "watch_accelerometer",
                    "samples": [
                        {"offset_ms": 0, "values": {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}},
                    ],
                }
            )
            ws.send_json(
                {
                    "type": "stream_batch",
                    "source_mode": "live",
                    "stream_name": "watch_heart_rate",
                    "samples": [
                        {"offset_ms": 0, "values": {"hr_bpm": 72}},
                    ],
                }
            )
            policy_notice = ws.receive_json()
            fallback_notice = ws.receive_json()
            payload = ws.receive_json()

    assert add_calls == [
        ("watch_accelerometer", 0, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}),
        ("watch_heart_rate", 0, {"hr_bpm": 72}),
    ]
    assert policy_notice["type"] == "error"
    assert policy_notice["code"] == "polar_primary_policy_fallback"
    assert fallback_notice["type"] == "error"
    assert fallback_notice["code"] == "heart_source_fallback_active"
    assert payload["type"] == "inference"
    assert payload["heart_source"] == "watch_heart_rate"
    assert payload["heart_source_fallback_active"] is True


@pytest.mark.parametrize("source_mode", ["simulated", "unknown", "replay"])
def test_live_stream_batch_rejects_non_live_source_modes(monkeypatch, source_mode: str) -> None:
    add_calls: list[tuple[str, int, dict[str, object]]] = []

    monkeypatch.setattr(
        api.StreamBuffer,
        "add",
        lambda self, stream_name, offset_ms, values: add_calls.append((stream_name, offset_ms, values)),
    )

    with _open_client() as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json(
                {
                    "type": "stream_batch",
                    "source_mode": source_mode,
                    "stream_name": "watch_heart_rate",
                    "samples": [{"offset_ms": 0, "values": {"hr_bpm": 72}}],
                }
            )
            payload = ws.receive_json()

    assert add_calls == []
    assert payload["type"] == "error"
    assert payload["code"] == "live_source_required"
    assert payload["detail"] == f"stream_batch requires source_mode=live; got {source_mode}"


def test_live_stream_batch_rejects_missing_source_mode(monkeypatch) -> None:
    add_calls: list[tuple[str, int, dict[str, object]]] = []

    monkeypatch.setattr(
        api.StreamBuffer,
        "add",
        lambda self, stream_name, offset_ms, values: add_calls.append((stream_name, offset_ms, values)),
    )

    with _open_client() as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json(
                {
                    "type": "stream_batch",
                    "stream_name": "watch_accelerometer",
                    "samples": [{"offset_ms": 0, "values": {"acc_x_g": 0.1}}],
                }
            )
            payload = ws.receive_json()

    assert add_calls == []
    assert payload["type"] == "error"
    assert payload["code"] == "live_source_required"
    assert payload["detail"] == "stream_batch requires source_mode=live; got missing"
