from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
from typing import Any

from fastapi.testclient import TestClient
import pytest

from ingest_api import api as api_module
from ingest_api import service as service_module
from ingest_api.config import Settings
from ingest_api.errors import ConflictError, NotFoundError


@dataclass
class _FakeState:
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    idempotency_records: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    next_artifact_id: int = 1


class _FakeConnection:
    def __init__(self, state: _FakeState) -> None:
        self.state = state

    @contextmanager
    def transaction(self):
        yield


class _FakeDatabase:
    last_instance: _FakeDatabase | None = None

    def __init__(self, _: str) -> None:
        self.state = _FakeState()
        _FakeDatabase.last_instance = self

    @contextmanager
    def connection(self):
        yield _FakeConnection(self.state)


class _FakeStorage:
    last_instance: _FakeStorage | None = None

    def __init__(self, _: Settings) -> None:
        self.objects: dict[str, bytes] = {}
        _FakeStorage.last_instance = self

    def ensure_bucket(self) -> None:
        return

    def create_put_target(
        self,
        object_key: str,
        content_type: str,
        presign_endpoint_override: str | None = None,
    ) -> tuple[str, datetime, dict[str, str]]:
        del presign_endpoint_override
        return (
            f"http://fake-s3.local/{object_key}",
            datetime.now(timezone.utc) + timedelta(minutes=15),
            {"Content-Type": content_type},
        )

    def head_object(self, object_key: str) -> dict[str, Any]:
        payload = self.objects.get(object_key)
        if payload is None:
            raise ConflictError(
                code="artifact_object_missing",
                message="Artifact object is missing in object storage",
                details={"object_key": object_key},
            )
        return {
            "ContentLength": len(payload),
            "ETag": f'"{sha256(payload).hexdigest()[:16]}"',
        }

    def read_object(self, object_key: str) -> bytes:
        payload = self.objects.get(object_key)
        if payload is None:
            raise ConflictError(
                code="artifact_object_missing",
                message="Artifact object is missing in object storage",
                details={"object_key": object_key},
            )
        return payload

    def put_object(self, object_key: str, payload: bytes) -> None:
        self.objects[object_key] = payload


class _FakeIngestRepository:
    REQUIRED_ARTIFACT_ROLES = {
        "manifest_session",
        "manifest_subject",
        "manifest_devices",
        "manifest_streams",
        "manifest_segments",
        "checksums",
    }

    def __init__(self, conn: _FakeConnection) -> None:
        self._state = conn.state

    def get_idempotency_record(self, operation_key: str, idempotency_key: str) -> dict[str, Any] | None:
        return self._state.idempotency_records.get((operation_key, idempotency_key))

    def save_idempotency_record(
        self,
        operation_key: str,
        idempotency_key: str,
        request_body: bytes,
        response_payload: dict[str, Any],
        status_code: int,
        session_id: str | None,
    ) -> None:
        request_hash = sha256(request_body).hexdigest()
        key = (operation_key, idempotency_key)
        existing = self._state.idempotency_records.get(key)
        if existing is not None and existing["request_hash"] != request_hash:
            raise ConflictError(
                code="idempotency_key_payload_mismatch",
                message="Idempotency-Key was already used with a different payload",
            )
        self._state.idempotency_records[key] = {
            "request_hash": request_hash,
            "response_payload": response_payload,
            "status_code": status_code,
            "session_id": session_id,
        }

    def assert_idempotency_match(self, row: dict[str, Any], request_body: bytes) -> dict[str, Any]:
        if row["request_hash"] != sha256(request_body).hexdigest():
            raise ConflictError(
                code="idempotency_key_payload_mismatch",
                message="Idempotency-Key was already used with a different payload",
            )
        return row["response_payload"]

    def create_ingest_session(self, request) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        session_id = request.session.session_id
        if session_id in self._state.sessions:
            raise ConflictError(
                code="raw_session_already_exists",
                message="Session with this session_id already exists",
                details={"session_id": session_id},
            )

        now = datetime.now(timezone.utc)
        storage_root_prefix = f"raw-sessions/{session_id}"

        self._state.sessions[session_id] = {
            "session_id": session_id,
            "subject_id": request.subject.subject_id,
            "session_status": request.session.status,
            "ingest_status": "uploading",
            "schema_version": request.session.schema_version,
            "protocol_version": request.session.protocol_version,
            "storage_root_prefix": storage_root_prefix,
            "checksum_file_path": None,
            "package_checksum_sha256": None,
            "created_at_utc": now,
            "updated_at_utc": now,
            "ingest_finalized_at_utc": None,
            "ingested_at_utc": None,
            "last_error": None,
            "streams": [
                {
                    "stream_name": stream.stream_name,
                    "file_ref": stream.file_ref,
                    "checksum_sha256": stream.checksum_sha256,
                }
                for stream in request.streams
            ],
        }

        rows: dict[str, dict[str, Any]] = {}
        for artifact in request.artifacts:
            artifact_id = self._state.next_artifact_id
            self._state.next_artifact_id += 1
            rows[artifact.artifact_path] = {
                "artifact_id": artifact_id,
                "artifact_path": artifact.artifact_path,
                "artifact_role": artifact.artifact_role,
                "stream_name": artifact.stream_name,
                "content_type": artifact.content_type,
                "byte_size": artifact.byte_size,
                "checksum_sha256": artifact.checksum_sha256,
                "object_key": f"{storage_root_prefix}/{artifact.artifact_path}",
                "upload_status": "pending",
                "upload_attempt_count": 0,
                "storage_etag": None,
                "last_error": None,
            }
        self._state.artifacts[session_id] = rows

        return {
            "session_id": session_id,
            "ingest_status": "uploading",
            "created_at_utc": now,
            "expected_artifact_count": len(rows),
        }, list(rows.values())

    def get_raw_state(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        counts = self.get_artifact_counts(session_id)
        missing_required = self.get_missing_required_artifacts(session_id)

        return {
            "session_id": session["session_id"],
            "subject_id": session["subject_id"],
            "session_status": session["session_status"],
            "ingest_status": session["ingest_status"],
            "schema_version": session["schema_version"],
            "protocol_version": session["protocol_version"],
            "storage_root_prefix": session["storage_root_prefix"],
            "checksum_file_path": session["checksum_file_path"],
            "package_checksum_sha256": session["package_checksum_sha256"],
            "expected_artifact_count": counts["total"],
            "uploaded_artifact_count": counts["uploaded"],
            "verified_artifact_count": counts["verified"],
            "missing_required_artifacts": missing_required,
            "created_at_utc": session["created_at_utc"],
            "updated_at_utc": session["updated_at_utc"],
            "ingest_finalized_at_utc": session["ingest_finalized_at_utc"],
            "ingested_at_utc": session["ingested_at_utc"],
            "last_error": session["last_error"],
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self._state.sessions.get(session_id)
        if session is None:
            raise NotFoundError(
                code="raw_session_not_found",
                message="Raw session ingest state is not found",
                details={"session_id": session_id},
            )
        return session

    def assert_session_can_accept_uploads(self, session: dict[str, Any]) -> None:
        if session["ingest_status"] not in {"uploading", "uploaded"}:
            raise ConflictError(
                code="ingest_status_conflict",
                message="Session cannot accept uploads in current ingest status",
                details={"ingest_status": session["ingest_status"]},
            )

    def get_artifacts_by_paths(self, session_id: str, artifact_paths: list[str]) -> list[dict[str, Any]]:
        rows = self._state.artifacts[session_id]
        return [rows[path] for path in artifact_paths if path in rows]

    def increment_upload_attempt(self, session_id: str, artifact_path: str) -> None:
        self._state.artifacts[session_id][artifact_path]["upload_attempt_count"] += 1

    def set_session_ingest_status(self, session_id: str, ingest_status: str) -> None:
        session = self.get_session(session_id)
        session["ingest_status"] = ingest_status
        session["updated_at_utc"] = datetime.now(timezone.utc)

    def insert_audit_log(self, **_: Any) -> None:
        return

    def get_artifact_by_path(self, session_id: str, artifact_path: str) -> dict[str, Any]:
        artifact = self._state.artifacts.get(session_id, {}).get(artifact_path)
        if artifact is None:
            raise NotFoundError(
                code="artifact_not_found",
                message="Artifact descriptor was not found",
                details={"session_id": session_id, "artifact_path": artifact_path},
            )
        return artifact

    def mark_artifact_failed(self, session_id: str, artifact_path: str, code: str, message: str) -> None:
        artifact = self.get_artifact_by_path(session_id, artifact_path)
        artifact["upload_status"] = "failed"
        artifact["last_error"] = {"code": code, "message": message}

    def mark_artifact_uploaded(self, session_id: str, artifact_path: str, storage_etag: str | None) -> None:
        artifact = self.get_artifact_by_path(session_id, artifact_path)
        artifact["upload_status"] = "uploaded"
        artifact["storage_etag"] = storage_etag

    def get_artifact_counts(self, session_id: str) -> dict[str, int]:
        rows = self._state.artifacts[session_id].values()
        return {
            "total": len(self._state.artifacts[session_id]),
            "pending": sum(1 for row in rows if row["upload_status"] == "pending"),
            "uploaded": sum(1 for row in rows if row["upload_status"] == "uploaded"),
            "verified": sum(1 for row in rows if row["upload_status"] == "verified"),
            "failed": sum(1 for row in rows if row["upload_status"] == "failed"),
        }

    def get_missing_required_artifacts(self, session_id: str) -> list[str]:
        roles = {row["artifact_role"] for row in self._state.artifacts[session_id].values()}
        return sorted(self.REQUIRED_ARTIFACT_ROLES - roles)

    def stream_manifest_consistency_ok(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        artifacts = self._state.artifacts[session_id]
        for stream in session["streams"]:
            artifact = artifacts.get(stream["file_ref"])
            if artifact is None:
                return False
            if artifact["checksum_sha256"] != stream["checksum_sha256"]:
                return False
        return True

    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._state.artifacts[session_id].values())

    def list_uploaded_or_verified_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        return [
            row
            for row in self._state.artifacts[session_id].values()
            if row["upload_status"] in {"uploaded", "verified"}
        ]

    def mark_artifact_verified(self, session_id: str, artifact_path: str) -> None:
        artifact = self.get_artifact_by_path(session_id, artifact_path)
        artifact["upload_status"] = "verified"

    def set_session_finalize_result(
        self,
        session_id: str,
        ingest_status: str,
        checksum_file_path: str,
        package_checksum_sha256: str,
        last_error_code: str | None,
        last_error_message: str | None,
    ) -> datetime:
        finalized_at = datetime.now(timezone.utc)
        session = self.get_session(session_id)
        session["ingest_status"] = ingest_status
        session["checksum_file_path"] = checksum_file_path
        session["package_checksum_sha256"] = package_checksum_sha256
        session["ingest_finalized_at_utc"] = finalized_at
        session["updated_at_utc"] = finalized_at
        session["ingested_at_utc"] = finalized_at if ingest_status == "ingested" else None
        if last_error_code and last_error_message:
            session["last_error"] = {"code": last_error_code, "message": last_error_message}
        else:
            session["last_error"] = None
        return finalized_at


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(api_module, "Database", _FakeDatabase)
    monkeypatch.setattr(api_module, "S3Storage", _FakeStorage)
    monkeypatch.setattr(service_module, "IngestRepository", _FakeIngestRepository)

    app = api_module.create_app(settings=Settings.from_env())
    with TestClient(app) as test_client:
        yield test_client


def _build_fixture_payload(session_id: str = "session-c4-001") -> tuple[dict[str, Any], dict[str, bytes], str]:
    artifact_contents: dict[str, bytes] = {
        "manifest/session.json": json.dumps({"session_id": session_id}, separators=(",", ":")).encode("utf-8"),
        "manifest/subject.json": b'{"subject_id":"subject-001"}',
        "manifest/devices.json": b'[{"device_id":"phone-1"}]',
        "manifest/segments.json": b'[{"segment_id":"seg-1"}]',
        "manifest/streams.json": b'[{"stream_name":"watch_heart_rate"}]',
        "streams/watch_heart_rate/samples.csv": b"timestamp_utc,bpm\n2026-03-22T00:00:00Z,71\n",
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
            "ended_at_utc": "2026-03-22T00:05:00Z",
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
                "ended_at_utc": "2026-03-22T00:05:00Z",
                "planned": True,
            }
        ],
        "streams": [
            {
                "stream_id": "stream-watch-hr",
                "device_id": "phone-1",
                "stream_name": "watch_heart_rate",
                "stream_kind": "timeseries",
                "sample_count": 1,
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


def test_ingest_lifecycle_with_fixture_package(client: TestClient) -> None:
    payload, artifact_contents, checksums_sha = _build_fixture_payload()

    create_response = client.post(
        "/v1/raw-sessions",
        json=payload,
        headers={"Idempotency-Key": "c4-create-001"},
    )
    assert create_response.status_code == 201
    create_body = create_response.json()
    assert create_body["session_id"] == payload["session"]["session_id"]
    assert create_body["expected_artifact_count"] == len(payload["artifacts"])

    # Retry with same idempotency key and payload must return the cached 201 response.
    retry_create = client.post(
        "/v1/raw-sessions",
        json=payload,
        headers={"Idempotency-Key": "c4-create-001"},
    )
    assert retry_create.status_code == 201
    assert retry_create.json()["session_id"] == create_body["session_id"]

    storage = _FakeStorage.last_instance
    assert storage is not None

    by_path = {artifact["artifact_path"]: artifact for artifact in payload["artifacts"]}
    completed_artifacts: list[dict[str, Any]] = []

    for target in create_body["upload_targets"]:
        artifact_path = target["artifact_path"]
        storage.put_object(target["object_key"], artifact_contents[artifact_path])
        declared = by_path[artifact_path]
        completed_artifacts.append(
            {
                "artifact_id": target["artifact_id"],
                "artifact_path": artifact_path,
                "byte_size": declared["byte_size"],
                "checksum_sha256": declared["checksum_sha256"],
            }
        )

    presign_response = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/artifacts/presign",
        json={"artifact_paths": ["manifest/session.json"]},
    )
    assert presign_response.status_code == 200
    assert presign_response.json()["session_id"] == create_body["session_id"]

    complete_payload = {"completed_artifacts": completed_artifacts}
    complete_response = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/artifacts/complete",
        json=complete_payload,
        headers={"Idempotency-Key": "c4-complete-001"},
    )
    assert complete_response.status_code == 200
    complete_body = complete_response.json()
    assert complete_body["ingest_status"] == "uploaded"
    assert complete_body["pending_artifact_count"] == 0
    assert complete_body["failed_artifact_count"] == 0

    retry_complete = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/artifacts/complete",
        json=complete_payload,
        headers={"Idempotency-Key": "c4-complete-001"},
    )
    assert retry_complete.status_code == 200
    assert retry_complete.json() == complete_body

    finalize_payload = {
        "package_checksum_sha256": checksums_sha,
        "checksum_file_path": "checksums/SHA256SUMS",
    }
    finalize_response = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/finalize",
        json=finalize_payload,
        headers={"Idempotency-Key": "c4-finalize-001"},
    )
    assert finalize_response.status_code == 200
    finalize_body = finalize_response.json()
    assert finalize_body["ingest_status"] == "ingested"
    assert finalize_body["validation_summary"]["required_artifacts_ok"] is True
    assert finalize_body["validation_summary"]["checksum_ok"] is True
    assert finalize_body["validation_summary"]["stream_manifest_ok"] is True
    assert finalize_body["validation_summary"]["error_count"] == 0

    retry_finalize = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/finalize",
        json=finalize_payload,
        headers={"Idempotency-Key": "c4-finalize-001"},
    )
    assert retry_finalize.status_code == 200
    assert retry_finalize.json() == finalize_body

    state_response = client.get(f"/v1/raw-sessions/{create_body['session_id']}")
    assert state_response.status_code == 200
    state = state_response.json()
    assert state["ingest_status"] == "ingested"
    assert state["verified_artifact_count"] == len(payload["artifacts"])
    assert state["missing_required_artifacts"] == []
    assert state["checksum_file_path"] == "checksums/SHA256SUMS"


def test_ingest_contract_routes_match_openapi(client: TestClient) -> None:
    contract_path = Path(__file__).resolve().parents[3] / "contracts/http/raw-session-ingest.openapi.yaml"
    contract_text = contract_path.read_text(encoding="utf-8")

    expected_operation_ids = set(re.findall(r"operationId:\\s*([A-Za-z0-9_]+)", contract_text))
    assert expected_operation_ids

    openapi_doc = client.get("/openapi.json")
    assert openapi_doc.status_code == 200
    openapi = openapi_doc.json()

    actual_operation_ids: set[str] = set()
    for path_item in openapi["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "operationId" in operation:
                actual_operation_ids.add(operation["operationId"])

    assert expected_operation_ids.issubset(actual_operation_ids)

    # Explicitly pin ingest lifecycle routes from the contract.
    expected_routes = {
        ("/v1/raw-sessions", "post"),
        ("/v1/raw-sessions/{session_id}", "get"),
        ("/v1/raw-sessions/{session_id}/artifacts/presign", "post"),
        ("/v1/raw-sessions/{session_id}/artifacts/complete", "post"),
        ("/v1/raw-sessions/{session_id}/finalize", "post"),
    }
    for path, method in expected_routes:
        assert path in openapi["paths"]
        assert method in openapi["paths"][path]


def test_complete_idempotency_key_rejects_different_payload(client: TestClient) -> None:
    payload, artifact_contents, _ = _build_fixture_payload(session_id="session-c4-002")

    create_response = client.post(
        "/v1/raw-sessions",
        json=payload,
        headers={"Idempotency-Key": "c4-create-002"},
    )
    assert create_response.status_code == 201
    create_body = create_response.json()

    storage = _FakeStorage.last_instance
    assert storage is not None

    by_path = {artifact["artifact_path"]: artifact for artifact in payload["artifacts"]}
    completed_artifacts: list[dict[str, Any]] = []
    for target in create_body["upload_targets"]:
        artifact_path = target["artifact_path"]
        storage.put_object(target["object_key"], artifact_contents[artifact_path])
        declared = by_path[artifact_path]
        completed_artifacts.append(
            {
                "artifact_id": target["artifact_id"],
                "artifact_path": artifact_path,
                "byte_size": declared["byte_size"],
                "checksum_sha256": declared["checksum_sha256"],
            }
        )

    ok_payload = {"completed_artifacts": completed_artifacts}
    ok_response = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/artifacts/complete",
        json=ok_payload,
        headers={"Idempotency-Key": "c4-complete-shared-key"},
    )
    assert ok_response.status_code == 200

    # Reusing the same idempotency key with a different payload must fail with conflict.
    bad_payload = {"completed_artifacts": completed_artifacts[:-1]}
    conflict_response = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/artifacts/complete",
        json=bad_payload,
        headers={"Idempotency-Key": "c4-complete-shared-key"},
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["error"]["code"] == "idempotency_key_payload_mismatch"


def test_finalize_fails_when_package_checksum_mismatch(client: TestClient) -> None:
    payload, artifact_contents, checksums_sha = _build_fixture_payload(session_id="session-c4-003")

    create_response = client.post("/v1/raw-sessions", json=payload)
    assert create_response.status_code == 201
    create_body = create_response.json()

    storage = _FakeStorage.last_instance
    assert storage is not None

    by_path = {artifact["artifact_path"]: artifact for artifact in payload["artifacts"]}
    completed_artifacts: list[dict[str, Any]] = []
    for target in create_body["upload_targets"]:
        artifact_path = target["artifact_path"]
        storage.put_object(target["object_key"], artifact_contents[artifact_path])
        declared = by_path[artifact_path]
        completed_artifacts.append(
            {
                "artifact_id": target["artifact_id"],
                "artifact_path": artifact_path,
                "byte_size": declared["byte_size"],
                "checksum_sha256": declared["checksum_sha256"],
            }
        )

    complete_response = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/artifacts/complete",
        json={"completed_artifacts": completed_artifacts},
    )
    assert complete_response.status_code == 200

    wrong_checksum = checksums_sha[:-1] + ("0" if checksums_sha[-1] != "0" else "1")
    finalize_response = client.post(
        f"/v1/raw-sessions/{create_body['session_id']}/finalize",
        json={
            "package_checksum_sha256": wrong_checksum,
            "checksum_file_path": "checksums/SHA256SUMS",
        },
    )
    assert finalize_response.status_code == 200
    body = finalize_response.json()
    assert body["ingest_status"] == "failed"
    assert body["validation_summary"]["checksum_ok"] is False
    assert body["validation_summary"]["error_count"] > 0
