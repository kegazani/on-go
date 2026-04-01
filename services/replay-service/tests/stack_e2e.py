from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from typing import Any
from urllib import error, request


@dataclass
class StackE2EConfig:
    ingest_base_url: str = "http://localhost:8080"
    replay_base_url: str = "http://localhost:8090"
    timeout_seconds: float = 20.0


class StackE2EError(RuntimeError):
    pass


def _json_request(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    body = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = request.Request(url=url, data=body, headers=req_headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            return resp.getcode(), json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def _put_bytes(url: str, payload: bytes, content_type: str, timeout_seconds: float) -> None:
    req = request.Request(
        url=url,
        data=payload,
        headers={"Content-Type": content_type},
        method="PUT",
    )
    with request.urlopen(req, timeout=timeout_seconds):
        return


def _build_fixture(session_id: str) -> tuple[dict[str, Any], dict[str, bytes], str]:
    artifact_contents: dict[str, bytes] = {
        "manifest/session.json": json.dumps({"session_id": session_id, "schema_version": "1.0.0"}).encode("utf-8"),
        "manifest/subject.json": b'{"subject_id":"subject-001","consent_version":"v1"}',
        "manifest/devices.json": b'[{"device_id":"phone-1","device_role":"coordinator_phone"}]',
        "manifest/segments.json": b'[{"segment_id":"seg-1","name":"baseline","order_index":0}]',
        "manifest/streams.json": b'[{"stream_name":"watch_heart_rate","stream_id":"stream-watch-hr"}]',
        "streams/watch_heart_rate/samples.csv": "\n".join(
            [
                "sample_index,offset_ms,timestamp_utc,hr_bpm",
                "0,0,2026-03-22T00:00:00Z,80",
                "1,1000,2026-03-22T00:00:01Z,82",
                "2,2000,2026-03-22T00:00:02Z,84",
            ]
        ).encode("utf-8"),
    }

    checksum_lines = [
        f"{sha256(payload).hexdigest()} {path}"
        for path, payload in sorted(artifact_contents.items())
    ]
    checksums_body = ("\n".join(checksum_lines) + "\n").encode("utf-8")
    artifact_contents["checksums/SHA256SUMS"] = checksums_body
    checksums_sha = sha256(checksums_body).hexdigest()

    payload: dict[str, Any] = {
        "session": {
            "session_id": session_id,
            "subject_id": "subject-001",
            "schema_version": "1.0.0",
            "protocol_version": "1.0.0",
            "session_type": "paired_capture",
            "status": "completed",
            "started_at_utc": "2026-03-22T00:00:00Z",
            "ended_at_utc": "2026-03-22T00:00:03Z",
            "timezone": "Europe/Moscow",
            "coordinator_device_id": "phone-1",
            "capture_app_version": "0.1.0",
        },
        "subject": {
            "subject_id": "subject-001",
            "consent_version": "v1",
        },
        "devices": [
            {
                "device_id": "phone-1",
                "device_role": "coordinator_phone",
                "manufacturer": "Apple",
                "model": "iPhone",
                "source_name": "ios-app",
            }
        ],
        "segments": [
            {
                "segment_id": "seg-1",
                "name": "baseline",
                "order_index": 0,
                "started_at_utc": "2026-03-22T00:00:00Z",
                "ended_at_utc": "2026-03-22T00:00:03Z",
                "planned": True,
            }
        ],
        "streams": [
            {
                "stream_id": "stream-watch-hr",
                "device_id": "phone-1",
                "stream_name": "watch_heart_rate",
                "stream_kind": "timeseries",
                "sample_count": 3,
                "file_ref": "streams/watch_heart_rate/samples.csv",
                "checksum_sha256": sha256(artifact_contents["streams/watch_heart_rate/samples.csv"]).hexdigest(),
            }
        ],
        "artifacts": [
            {
                "artifact_path": path,
                "artifact_role": role,
                "content_type": content_type,
                "byte_size": len(artifact_contents[path]),
                "checksum_sha256": sha256(artifact_contents[path]).hexdigest(),
                **({"stream_name": "watch_heart_rate"} if path == "streams/watch_heart_rate/samples.csv" else {}),
            }
            for path, role, content_type in [
                ("manifest/session.json", "manifest_session", "application/json"),
                ("manifest/subject.json", "manifest_subject", "application/json"),
                ("manifest/devices.json", "manifest_devices", "application/json"),
                ("manifest/segments.json", "manifest_segments", "application/json"),
                ("manifest/streams.json", "manifest_streams", "application/json"),
                ("streams/watch_heart_rate/samples.csv", "stream_samples", "text/csv"),
                ("checksums/SHA256SUMS", "checksums", "text/plain"),
            ]
        ],
    }
    return payload, artifact_contents, checksums_sha


def run_stack_e2e(config: StackE2EConfig | None = None) -> dict[str, Any]:
    cfg = config or StackE2EConfig()
    session_id = f"replay-d2-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    create_payload, artifact_contents, package_checksum = _build_fixture(session_id)

    status, body = _json_request("GET", f"{cfg.ingest_base_url}/health", timeout_seconds=cfg.timeout_seconds)
    if status != 200 or body.get("status") != "ok":
        raise StackE2EError(f"ingest health failed: status={status}, body={body}")

    status, body = _json_request("GET", f"{cfg.replay_base_url}/health", timeout_seconds=cfg.timeout_seconds)
    if status != 200 or body.get("status") != "ok":
        raise StackE2EError(f"replay health failed: status={status}, body={body}")

    status, create_response = _json_request(
        "POST",
        f"{cfg.ingest_base_url}/v1/raw-sessions",
        payload=create_payload,
        headers={"Idempotency-Key": f"{session_id}-create"},
        timeout_seconds=cfg.timeout_seconds,
    )
    if status != 201:
        raise StackE2EError(f"create failed: status={status}, body={create_response}")

    upload_targets = create_response["upload_targets"]
    by_path = {artifact["artifact_path"]: artifact for artifact in create_payload["artifacts"]}
    completed_artifacts: list[dict[str, Any]] = []

    for target in upload_targets:
        artifact_path = target["artifact_path"]
        artifact_payload = artifact_contents[artifact_path]
        required_headers = target.get("required_headers") or {}
        content_type = required_headers.get("Content-Type", "application/octet-stream")
        _put_bytes(
            url=target["upload_url"],
            payload=artifact_payload,
            content_type=content_type,
            timeout_seconds=cfg.timeout_seconds,
        )
        declared = by_path[artifact_path]
        completed_artifacts.append(
            {
                "artifact_id": target["artifact_id"],
                "artifact_path": artifact_path,
                "byte_size": declared["byte_size"],
                "checksum_sha256": declared["checksum_sha256"],
            }
        )

    status, complete_response = _json_request(
        "POST",
        f"{cfg.ingest_base_url}/v1/raw-sessions/{session_id}/artifacts/complete",
        payload={"completed_artifacts": completed_artifacts},
        headers={"Idempotency-Key": f"{session_id}-complete"},
        timeout_seconds=cfg.timeout_seconds,
    )
    if status != 200:
        raise StackE2EError(f"complete failed: status={status}, body={complete_response}")
    if complete_response.get("ingest_status") != "uploaded":
        raise StackE2EError(f"complete returned unexpected status: {complete_response}")

    status, finalize_response = _json_request(
        "POST",
        f"{cfg.ingest_base_url}/v1/raw-sessions/{session_id}/finalize",
        payload={
            "package_checksum_sha256": package_checksum,
            "checksum_file_path": "checksums/SHA256SUMS",
        },
        headers={"Idempotency-Key": f"{session_id}-finalize"},
        timeout_seconds=cfg.timeout_seconds,
    )
    if status != 200:
        raise StackE2EError(f"finalize failed: status={status}, body={finalize_response}")
    if finalize_response.get("ingest_status") != "ingested":
        raise StackE2EError(f"finalize returned unexpected status: {finalize_response}")

    status, manifest_response = _json_request(
        "GET",
        f"{cfg.replay_base_url}/v1/replay/sessions/{session_id}/manifest",
        timeout_seconds=cfg.timeout_seconds,
    )
    if status != 200:
        raise StackE2EError(f"manifest failed: status={status}, body={manifest_response}")

    streams = manifest_response.get("streams") or []
    if len(streams) != 1:
        raise StackE2EError(f"manifest streams mismatch: {streams}")
    stream = streams[0]
    if stream.get("stream_name") != "watch_heart_rate" or stream.get("available_for_replay") is not True:
        raise StackE2EError(f"manifest stream is not replayable: {stream}")

    status, window_response = _json_request(
        "POST",
        f"{cfg.replay_base_url}/v1/replay/sessions/{session_id}/windows",
        payload={
            "mode": "accelerated",
            "speed_multiplier": 2.0,
            "from_offset_ms": 500,
            "window_ms": 2000,
            "stream_names": ["watch_heart_rate"],
            "include_events": False,
            "max_samples_per_stream": 10,
        },
        timeout_seconds=cfg.timeout_seconds,
    )
    if status != 200:
        raise StackE2EError(f"window failed: status={status}, body={window_response}")

    samples = window_response.get("samples") or []
    if [sample.get("offset_ms") for sample in samples] != [1000, 2000]:
        raise StackE2EError(f"unexpected replay offsets: {samples}")
    if [sample.get("replay_at_offset_ms") for sample in samples] != [750, 1250]:
        raise StackE2EError(f"unexpected replay_at_offset_ms: {samples}")

    hr_values = [sample.get("values", {}).get("hr_bpm") for sample in samples]
    if hr_values != [82, 84]:
        raise StackE2EError(f"unexpected replay values: {samples}")

    if window_response.get("sample_count") != 2:
        raise StackE2EError(f"sample_count mismatch: {window_response}")

    return {
        "session_id": session_id,
        "manifest_stream_count": manifest_response.get("stream_count"),
        "window_sample_count": window_response.get("sample_count"),
        "window_event_count": window_response.get("event_count"),
    }


def main() -> int:
    config = StackE2EConfig(
        ingest_base_url=os.getenv("INGEST_BASE_URL", "http://localhost:8080"),
        replay_base_url=os.getenv("REPLAY_BASE_URL", "http://localhost:8090"),
        timeout_seconds=float(os.getenv("STACK_E2E_TIMEOUT_SECONDS", "20")),
    )
    try:
        result = run_stack_e2e(config)
    except Exception as exc:  # noqa: BLE001
        print(f"[stack-e2e] FAILED: {exc}")
        return 1

    print("[stack-e2e] OK")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
