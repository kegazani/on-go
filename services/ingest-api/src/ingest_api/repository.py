from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.types.json import Json

from ingest_api.errors import ConflictError, NotFoundError, ValidationError
from ingest_api.models import (
    ArtifactDescriptorInput,
    CreateRawSessionIngestRequest,
    SourceInfo,
)

REQUIRED_ARTIFACT_ROLES = {
    "manifest_session",
    "manifest_subject",
    "manifest_devices",
    "manifest_streams",
    "manifest_segments",
    "checksums",
}


class IngestRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_idempotency_record(self, operation_key: str, idempotency_key: str) -> dict[str, Any] | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT request_hash, response_payload, status_code
                FROM ingest.idempotency_records
                WHERE operation_key = %s AND idempotency_key = %s
                """,
                (operation_key, idempotency_key),
            )
            return cur.fetchone()

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

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingest.idempotency_records (
                    operation_key,
                    idempotency_key,
                    request_hash,
                    session_id,
                    response_payload,
                    status_code
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (operation_key, idempotency_key)
                DO UPDATE SET
                    response_payload = EXCLUDED.response_payload,
                    status_code = EXCLUDED.status_code,
                    updated_at = NOW()
                WHERE ingest.idempotency_records.request_hash = EXCLUDED.request_hash
                """,
                (
                    operation_key,
                    idempotency_key,
                    request_hash,
                    session_id,
                    Json(response_payload),
                    status_code,
                ),
            )
            if cur.rowcount == 0:
                raise ConflictError(
                    code="idempotency_key_payload_mismatch",
                    message="Idempotency-Key was already used with a different payload",
                )

    def assert_idempotency_match(self, row: dict[str, Any], request_body: bytes) -> dict[str, Any]:
        request_hash = sha256(request_body).hexdigest()
        if row["request_hash"] != request_hash:
            raise ConflictError(
                code="idempotency_key_payload_mismatch",
                message="Idempotency-Key was already used with a different payload",
            )
        return row["response_payload"]

    def create_ingest_session(self, request: CreateRawSessionIngestRequest) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        created_at_utc = datetime.now(timezone.utc)
        storage_root_prefix = f"raw-sessions/{request.session.session_id}"

        try:
            with self._conn.cursor() as cur:
                self._upsert_subject(cur, request)

                cur.execute(
                    """
                    INSERT INTO ingest.raw_sessions (
                        session_id,
                        subject_id,
                        schema_version,
                        protocol_version,
                        session_type,
                        session_status,
                        started_at_utc,
                        ended_at_utc,
                        timezone,
                        coordinator_device_id,
                        capture_app_version,
                        operator_mode,
                        session_environment,
                        notes,
                        planned_segment_count,
                        observed_segment_count,
                        stream_count,
                        export_completed_at_utc,
                        ingest_status,
                        ingest_requested_at_utc,
                        storage_root_prefix
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploading', %s, %s
                    )
                    """,
                    (
                        request.session.session_id,
                        request.session.subject_id,
                        request.session.schema_version,
                        request.session.protocol_version,
                        request.session.session_type,
                        request.session.status,
                        request.session.started_at_utc,
                        request.session.ended_at_utc,
                        request.session.timezone,
                        request.session.coordinator_device_id,
                        request.session.capture_app_version,
                        request.session.operator_mode,
                        Json(request.session.session_environment),
                        request.session.notes,
                        request.session.planned_segment_count,
                        request.session.observed_segment_count,
                        request.session.stream_count,
                        request.session.export_completed_at_utc,
                        created_at_utc,
                        storage_root_prefix,
                    ),
                )

                self._insert_devices(cur, request)
                self._insert_segments(cur, request)
                self._insert_streams(cur, request)
                artifacts = self._insert_artifacts(cur, request, storage_root_prefix)

                self.insert_audit_log(
                    session_id=request.session.session_id,
                    action_type="create_ingest",
                    source=request.source,
                    payload={
                        "expected_artifact_count": len(artifacts),
                        "storage_root_prefix": storage_root_prefix,
                    },
                )

        except psycopg.errors.UniqueViolation as exc:
            raise ConflictError(
                code="raw_session_already_exists",
                message="Session with this session_id already exists",
                details={"session_id": request.session.session_id},
            ) from exc

        session_row = {
            "session_id": request.session.session_id,
            "ingest_status": "uploading",
            "created_at_utc": created_at_utc,
            "expected_artifact_count": len(artifacts),
        }
        return session_row, artifacts

    def _upsert_subject(self, cur: psycopg.Cursor, request: CreateRawSessionIngestRequest) -> None:
        cur.execute(
            """
            INSERT INTO ingest.subjects (
                subject_id,
                cohort,
                study_group,
                sex,
                age_range,
                consent_version,
                baseline_notes,
                metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)
            ON CONFLICT (subject_id)
            DO UPDATE SET
                cohort = EXCLUDED.cohort,
                study_group = EXCLUDED.study_group,
                sex = EXCLUDED.sex,
                age_range = EXCLUDED.age_range,
                consent_version = EXCLUDED.consent_version,
                baseline_notes = EXCLUDED.baseline_notes,
                updated_at = NOW()
            """,
            (
                request.subject.subject_id,
                request.subject.cohort,
                request.subject.study_group,
                request.subject.sex,
                request.subject.age_range,
                request.subject.consent_version,
                request.subject.baseline_notes,
            ),
        )

    def _insert_devices(self, cur: psycopg.Cursor, request: CreateRawSessionIngestRequest) -> None:
        for device in request.devices:
            cur.execute(
                """
                INSERT INTO ingest.session_devices (
                    session_id,
                    device_id,
                    device_role,
                    manufacturer,
                    model,
                    firmware_version,
                    source_name,
                    connection_started_at_utc,
                    connection_ended_at_utc,
                    metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)
                """,
                (
                    request.session.session_id,
                    device.device_id,
                    device.device_role,
                    device.manufacturer,
                    device.model,
                    device.firmware_version,
                    device.source_name,
                    device.connection_started_at_utc,
                    device.connection_ended_at_utc,
                ),
            )

    def _insert_segments(self, cur: psycopg.Cursor, request: CreateRawSessionIngestRequest) -> None:
        for segment in request.segments:
            cur.execute(
                """
                INSERT INTO ingest.session_segments (
                    session_id,
                    segment_id,
                    name,
                    order_index,
                    started_at_utc,
                    ended_at_utc,
                    planned,
                    notes,
                    metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)
                """,
                (
                    request.session.session_id,
                    segment.segment_id,
                    segment.name,
                    segment.order_index,
                    segment.started_at_utc,
                    segment.ended_at_utc,
                    segment.planned,
                    segment.notes,
                ),
            )

    def _insert_streams(self, cur: psycopg.Cursor, request: CreateRawSessionIngestRequest) -> None:
        for stream in request.streams:
            cur.execute(
                """
                INSERT INTO ingest.session_streams (
                    session_id,
                    stream_id,
                    device_id,
                    stream_name,
                    stream_kind,
                    unit_schema,
                    sample_count,
                    started_at_utc,
                    ended_at_utc,
                    file_ref,
                    checksum_sha256,
                    missing_intervals,
                    metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)
                """,
                (
                    request.session.session_id,
                    stream.stream_id,
                    stream.device_id,
                    stream.stream_name,
                    stream.stream_kind,
                    Json(stream.unit_schema),
                    stream.sample_count,
                    stream.started_at_utc,
                    stream.ended_at_utc,
                    stream.file_ref,
                    stream.checksum_sha256,
                    Json([interval.model_dump(mode="json") for interval in stream.missing_intervals]),
                ),
            )

    def _insert_artifacts(
        self,
        cur: psycopg.Cursor,
        request: CreateRawSessionIngestRequest,
        storage_root_prefix: str,
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for artifact in request.artifacts:
            object_key = self._build_object_key(storage_root_prefix, artifact)
            cur.execute(
                """
                INSERT INTO ingest.ingest_artifacts (
                    session_id,
                    artifact_path,
                    artifact_role,
                    stream_name,
                    content_type,
                    byte_size,
                    checksum_sha256,
                    object_key,
                    upload_status,
                    metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', '{}'::jsonb)
                RETURNING artifact_id, artifact_path, artifact_role, object_key, content_type
                """,
                (
                    request.session.session_id,
                    artifact.artifact_path,
                    artifact.artifact_role,
                    artifact.stream_name,
                    artifact.content_type,
                    artifact.byte_size,
                    artifact.checksum_sha256,
                    object_key,
                ),
            )
            row = cur.fetchone()
            if row:
                artifacts.append(row)

        return artifacts

    @staticmethod
    def _build_object_key(storage_root_prefix: str, artifact: ArtifactDescriptorInput) -> str:
        artifact_path = artifact.artifact_path.lstrip("/")
        return f"{storage_root_prefix}/{artifact_path}"

    def insert_audit_log(
        self,
        session_id: str,
        action_type: str,
        source: SourceInfo | None,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> None:
        actor_type = source.actor_type if source and source.actor_type else "service"
        actor_id = source.actor_id if source else None

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingest.ingest_audit_log (
                    session_id,
                    action_type,
                    actor_type,
                    actor_id,
                    idempotency_key,
                    payload
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    action_type,
                    actor_type,
                    actor_id,
                    idempotency_key,
                    Json(payload),
                ),
            )

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, subject_id, ingest_status, session_status, schema_version, protocol_version,
                       storage_root_prefix, checksum_file_path, package_checksum_sha256,
                       ingest_finalized_at_utc, ingested_at_utc,
                       last_error_code, last_error_message,
                       created_at, updated_at
                FROM ingest.raw_sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise NotFoundError(
                code="session_not_found",
                message="Session not found",
                details={"session_id": session_id},
            )
        return row

    def get_artifact_counts(self, session_id: str) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS expected,
                    COUNT(*) FILTER (WHERE upload_status IN ('uploaded', 'verified')) AS uploaded,
                    COUNT(*) FILTER (WHERE upload_status = 'verified') AS verified,
                    COUNT(*) FILTER (WHERE upload_status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE upload_status = 'failed') AS failed
                FROM ingest.ingest_artifacts
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
        return {
            "expected": int(row["expected"]),
            "uploaded": int(row["uploaded"]),
            "verified": int(row["verified"]),
            "pending": int(row["pending"]),
            "failed": int(row["failed"]),
        }

    def get_missing_required_artifacts(self, session_id: str) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_role,
                       COUNT(*) FILTER (WHERE upload_status IN ('uploaded', 'verified')) AS ready_count
                FROM ingest.ingest_artifacts
                WHERE session_id = %s AND artifact_role = ANY(%s)
                GROUP BY artifact_role
                """,
                (session_id, list(REQUIRED_ARTIFACT_ROLES)),
            )
            role_rows = cur.fetchall()

        ready_by_role = {row["artifact_role"]: int(row["ready_count"]) for row in role_rows}

        missing: list[str] = []
        for role in sorted(REQUIRED_ARTIFACT_ROLES):
            if ready_by_role.get(role, 0) == 0:
                missing.append(role)
        return missing

    def get_artifacts_by_paths(self, session_id: str, artifact_paths: list[str]) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, artifact_path, artifact_role, object_key, content_type, byte_size,
                       checksum_sha256, upload_status
                FROM ingest.ingest_artifacts
                WHERE session_id = %s AND artifact_path = ANY(%s)
                ORDER BY artifact_path
                """,
                (session_id, artifact_paths),
            )
            return cur.fetchall()

    def increment_upload_attempt(self, session_id: str, artifact_path: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest.ingest_artifacts
                SET upload_attempt_count = upload_attempt_count + 1,
                    error_code = NULL,
                    error_message = NULL
                WHERE session_id = %s AND artifact_path = %s
                """,
                (session_id, artifact_path),
            )

    def assert_session_can_accept_uploads(self, session: dict[str, Any]) -> None:
        if session["ingest_status"] in {"validating", "ingested", "cancelled"}:
            raise ConflictError(
                code="ingest_status_conflict",
                message="Session is not accepting uploads in current status",
                details={"ingest_status": session["ingest_status"]},
            )

    def mark_artifact_failed(self, session_id: str, artifact_path: str, code: str, message: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest.ingest_artifacts
                SET upload_status = 'failed',
                    error_code = %s,
                    error_message = %s,
                    uploaded_at_utc = NULL,
                    verified_at_utc = NULL
                WHERE session_id = %s AND artifact_path = %s
                """,
                (code, message, session_id, artifact_path),
            )

    def mark_artifact_uploaded(
        self,
        session_id: str,
        artifact_path: str,
        storage_etag: str | None,
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest.ingest_artifacts
                SET upload_status = 'uploaded',
                    storage_etag = %s,
                    uploaded_at_utc = NOW(),
                    error_code = NULL,
                    error_message = NULL
                WHERE session_id = %s AND artifact_path = %s
                """,
                (storage_etag, session_id, artifact_path),
            )

    def set_session_ingest_status(
        self,
        session_id: str,
        ingest_status: str,
        last_error_code: str | None = None,
        last_error_message: str | None = None,
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest.raw_sessions
                SET ingest_status = %s,
                    last_error_code = %s,
                    last_error_message = %s
                WHERE session_id = %s
                """,
                (ingest_status, last_error_code, last_error_message, session_id),
            )

    def get_artifact_by_path(self, session_id: str, artifact_path: str) -> dict[str, Any]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, artifact_path, artifact_role, stream_name, object_key,
                       content_type, byte_size, checksum_sha256, upload_status, storage_etag
                FROM ingest.ingest_artifacts
                WHERE session_id = %s AND artifact_path = %s
                """,
                (session_id, artifact_path),
            )
            row = cur.fetchone()

        if row is None:
            raise ValidationError(
                code="artifact_not_found",
                message="Artifact path is unknown for this session",
                details={"artifact_path": artifact_path, "session_id": session_id},
            )
        return row

    def list_uploaded_or_verified_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, artifact_path, artifact_role, object_key, byte_size,
                       checksum_sha256, upload_status
                FROM ingest.ingest_artifacts
                WHERE session_id = %s AND upload_status IN ('uploaded', 'verified')
                ORDER BY artifact_path
                """,
                (session_id,),
            )
            return cur.fetchall()

    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT artifact_id, artifact_path, artifact_role, object_key, byte_size,
                       checksum_sha256, upload_status
                FROM ingest.ingest_artifacts
                WHERE session_id = %s
                ORDER BY artifact_path
                """,
                (session_id,),
            )
            return cur.fetchall()

    def mark_artifact_verified(self, session_id: str, artifact_path: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest.ingest_artifacts
                SET upload_status = 'verified',
                    verified_at_utc = NOW(),
                    error_code = NULL,
                    error_message = NULL
                WHERE session_id = %s AND artifact_path = %s
                """,
                (session_id, artifact_path),
            )

    def set_session_finalize_result(
        self,
        session_id: str,
        ingest_status: str,
        checksum_file_path: str,
        package_checksum_sha256: str,
        last_error_code: str | None,
        last_error_message: str | None,
    ) -> datetime:
        now = datetime.now(timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest.raw_sessions
                SET ingest_status = %s,
                    checksum_file_path = %s,
                    package_checksum_sha256 = %s,
                    ingest_finalized_at_utc = %s,
                    ingested_at_utc = CASE WHEN %s = 'ingested' THEN %s ELSE ingested_at_utc END,
                    last_error_code = %s,
                    last_error_message = %s
                WHERE session_id = %s
                """,
                (
                    ingest_status,
                    checksum_file_path,
                    package_checksum_sha256,
                    now,
                    ingest_status,
                    now,
                    last_error_code,
                    last_error_message,
                    session_id,
                ),
            )
        return now

    def stream_manifest_consistency_ok(self, session_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS broken_links
                FROM ingest.session_streams s
                LEFT JOIN ingest.ingest_artifacts a
                  ON a.session_id = s.session_id
                 AND a.artifact_path = s.file_ref
                WHERE s.session_id = %s
                  AND (
                    a.artifact_id IS NULL
                    OR a.checksum_sha256 <> s.checksum_sha256
                  )
                """,
                (session_id,),
            )
            row = cur.fetchone()
        return int(row["broken_links"]) == 0

    def assert_checksum_artifact_ready(self, session_id: str, checksum_file_path: str) -> dict[str, Any]:
        artifact = self.get_artifact_by_path(session_id=session_id, artifact_path=checksum_file_path)
        if artifact["upload_status"] not in {"uploaded", "verified"}:
            raise ValidationError(
                code="checksum_artifact_not_uploaded",
                message="Checksum artifact must be uploaded before finalize",
                details={"checksum_file_path": checksum_file_path},
            )
        return artifact

    def assert_all_artifacts_uploaded(self, session_id: str) -> None:
        counts = self.get_artifact_counts(session_id)
        if counts["pending"] > 0 or counts["failed"] > 0:
            raise ValidationError(
                code="artifacts_not_ready",
                message="Finalize requires all artifacts in uploaded state",
                details={
                    "pending_artifact_count": counts["pending"],
                    "failed_artifact_count": counts["failed"],
                },
            )

    def get_raw_state(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        counts = self.get_artifact_counts(session_id)
        missing = self.get_missing_required_artifacts(session_id)

        last_error = None
        if session["last_error_code"] or session["last_error_message"]:
            last_error = {
                "code": session["last_error_code"] or "unknown",
                "message": session["last_error_message"] or "",
                "details": None,
            }

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
            "expected_artifact_count": counts["expected"],
            "uploaded_artifact_count": counts["uploaded"],
            "verified_artifact_count": counts["verified"],
            "missing_required_artifacts": missing,
            "created_at_utc": session["created_at"],
            "updated_at_utc": session["updated_at"],
            "ingest_finalized_at_utc": session["ingest_finalized_at_utc"],
            "ingested_at_utc": session["ingested_at_utc"],
            "last_error": last_error,
        }
