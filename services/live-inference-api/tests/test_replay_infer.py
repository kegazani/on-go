from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from live_inference_api import api as api_mod
from live_inference_api.api import create_app
from live_inference_api.config import Settings
from live_inference_api.loader import load_model_bundle
from live_inference_api.replay_infer import infer_from_replay_window_json, run_replay_infer

M7_5_RUNTIME_BUNDLE_DIR = Path(
    "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-5-runtime-bundle-export"
)
NO_MODEL_DIR = Path("/nonexistent-on-go-test-model-dir")


def _bundle():
    if not M7_5_RUNTIME_BUNDLE_DIR.exists():
        pytest.skip("m7-5 runtime bundle not present")
    return load_model_bundle(M7_5_RUNTIME_BUNDLE_DIR)


def test_infer_from_replay_window_json_skipped_no_acc() -> None:
    bundle = _bundle()
    out = infer_from_replay_window_json(
        window={
            "from_offset_ms": 0,
            "to_offset_ms": 5000,
            "samples": [
                {"stream_name": "polar_hr", "offset_ms": 0, "values": {"hr_bpm": 72.0}},
            ],
            "warnings": [],
        },
        bundle=bundle,
        context="public_app",
    )
    assert out["skipped"] is True
    assert out["skip_reason"] == "insufficient_streams"


def test_infer_from_replay_window_json_predicts() -> None:
    bundle = _bundle()
    out = infer_from_replay_window_json(
        window={
            "from_offset_ms": 0,
            "to_offset_ms": 15000,
            "samples": [
                {"stream_name": "watch_accelerometer", "offset_ms": 0, "values": {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}},
                {"stream_name": "polar_hr", "offset_ms": 0, "values": {"hr_bpm": 72.0}},
                {"stream_name": "polar_rr", "offset_ms": 0, "values": {"rr_ms": 820.0}},
                {"stream_name": "polar_rr", "offset_ms": 1000, "values": {"rr_ms": 810.0}},
            ],
            "warnings": ["x"],
        },
        bundle=bundle,
        context="public_app",
    )
    assert out["skipped"] is False
    assert out["heart_source"] == "polar_hr"
    assert "activity" in out
    assert out["replay_warnings"] == ["x"]


def test_run_replay_infer_mock_transport() -> None:
    bundle = _bundle()

    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if request.method == "GET" and "/manifest" in u:
            return httpx.Response(
                200,
                json={
                    "duration_ms": 10000,
                    "streams": [
                        {"stream_name": "watch_accelerometer", "available_for_replay": True},
                        {"stream_name": "polar_hr", "available_for_replay": True},
                        {"stream_name": "polar_rr", "available_for_replay": True},
                    ],
                },
            )
        if request.method == "POST" and "/windows" in u:
            body = json.loads(request.content.decode("utf-8"))
            fo = int(body["from_offset_ms"])
            samples = [
                {"stream_name": "watch_accelerometer", "offset_ms": fo, "values": {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}},
                {"stream_name": "polar_hr", "offset_ms": fo, "values": {"hr_bpm": 72.0}},
                {"stream_name": "polar_rr", "offset_ms": fo, "values": {"rr_ms": 820.0}},
            ]
            return httpx.Response(
                200,
                json={
                    "from_offset_ms": fo,
                    "to_offset_ms": fo + 10000,
                    "samples": samples,
                    "warnings": [],
                },
            )
        return httpx.Response(404, json={"error": "unexpected"})

    async def run() -> object:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await run_replay_infer(
                base_url="http://replay.test",
                session_id="sess-1",
                window_ms=10000,
                step_ms=5000,
                stream_names=None,
                context="public_app",
                bundle=bundle,
                client=client,
            )

    result = asyncio.run(run())
    assert "error" not in result
    assert result["session_id"] == "sess-1"
    assert len(result["windows"]) == 2


def test_run_replay_infer_manifest_404() -> None:
    bundle = _bundle()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": "not_found"}})

    async def run() -> object:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await run_replay_infer(
                base_url="http://replay.test",
                session_id="missing",
                window_ms=5000,
                step_ms=5000,
                stream_names=None,
                context="public_app",
                bundle=bundle,
                client=client,
            )

    result = asyncio.run(run())
    assert "error" in result
    assert result["error"]["http_status"] == 404


def test_replay_infer_endpoint_503_without_bundle(monkeypatch) -> None:
    monkeypatch.setattr(api_mod, "model_bundle", None)
    client = TestClient(create_app(Settings(model_dir=NO_MODEL_DIR)))
    r = client.post("/v1/replay/infer", json={"session_id": "abc"})
    assert r.status_code == 503
    r2 = client.post("/api/v1/replay/infer", json={"session_id": "abc"})
    assert r2.status_code == 503


def test_replay_infer_endpoint_200_mocked(monkeypatch) -> None:
    bundle = _bundle()
    monkeypatch.setattr(api_mod, "model_bundle", bundle)
    monkeypatch.setattr(
        api_mod,
        "run_replay_infer",
        AsyncMock(
            return_value={
                "session_id": "s",
                "duration_ms": 1,
                "windows": [],
                "stream_names": [],
                "window_ms": 1,
                "step_ms": 1,
            }
        ),
    )
    client = TestClient(create_app(Settings(model_dir=NO_MODEL_DIR)))
    r = client.post("/v1/replay/infer", json={"session_id": "abc"})
    assert r.status_code == 200
    assert r.json()["session_id"] == "s"
    r2 = client.post("/api/v1/replay/infer", json={"session_id": "abc"})
    assert r2.status_code == 200
    assert r2.json()["session_id"] == "s"
