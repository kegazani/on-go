from __future__ import annotations

from hashlib import sha256
import re
from typing import Any

from ingest_api.db import Database
from ingest_api.errors import ConflictError, ValidationError
from ingest_api.models import (
    ArtifactUploadTarget,
    CompleteArtifactsRequest,
    CompleteArtifactsResponse,
    CreateRawSessionIngestRequest,
    CreateRawSessionIngestResponse,
    FinalizeRawSessionRequest,
    FinalizeRawSessionResponse,
    PresignArtifactsRequest,
    PresignArtifactsResponse,
    RawSessionIngestState,
    ValidationSummary,
)
from ingest_api.repository import IngestRepository
from ingest_api.storage import S3Storage

SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class IngestService:
    def __init__(self, database: Database, storage: S3Storage) -> None:
        self._database = database
        self._storage = storage

    def create_raw_session(
        self,
        request: CreateRawSessionIngestRequest,
        idempotency_key: str | None,
        raw_body: bytes,
    ) -> CreateRawSessionIngestResponse:
        operation_key = "create_raw_session"

        with self._database.connection() as conn:
            with conn.transaction():
                repo = IngestRepository(conn)
                cached = self._maybe_restore_idempotent_response(
                    repo=repo,
                    operation_key=operation_key,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                )
                if cached is not None:
                    return CreateRawSessionIngestResponse.model_validate(cached)

                session_row, artifacts = repo.create_ingest_session(request)
                upload_targets = self._build_upload_targets(artifacts)

                response = CreateRawSessionIngestResponse(
                    session_id=session_row["session_id"],
                    ingest_status=session_row["ingest_status"],
                    created_at_utc=session_row["created_at_utc"],
                    expected_artifact_count=session_row["expected_artifact_count"],
                    upload_targets=upload_targets,
                    warnings=[],
                )

                if idempotency_key:
                    repo.save_idempotency_record(
                        operation_key=operation_key,
                        idempotency_key=idempotency_key,
                        request_body=raw_body,
                        response_payload=response.model_dump(mode="json"),
                        status_code=201,
                        session_id=request.session.session_id,
                    )

        return response

    def get_raw_session_state(self, session_id: str) -> RawSessionIngestState:
        with self._database.connection() as conn:
            repo = IngestRepository(conn)
            return RawSessionIngestState.model_validate(repo.get_raw_state(session_id))

    def presign_artifacts(self, session_id: str, request: PresignArtifactsRequest) -> PresignArtifactsResponse:
        with self._database.connection() as conn:
            with conn.transaction():
                repo = IngestRepository(conn)
                session = repo.get_session(session_id)
                repo.assert_session_can_accept_uploads(session)

                artifact_rows = repo.get_artifacts_by_paths(session_id, request.artifact_paths)
                by_path = {row["artifact_path"]: row for row in artifact_rows}

                missing_paths = sorted(set(request.artifact_paths) - set(by_path.keys()))
                if missing_paths:
                    raise ValidationError(
                        code="artifact_path_unknown",
                        message="One or more artifact_paths are unknown for this session",
                        details={"missing_artifact_paths": missing_paths},
                    )

                upload_targets: list[ArtifactUploadTarget] = []
                for artifact_path in request.artifact_paths:
                    artifact = by_path[artifact_path]
                    if artifact["upload_status"] not in {"pending", "failed"}:
                        raise ConflictError(
                            code="artifact_status_conflict",
                            message="Presign is allowed only for pending/failed artifacts",
                            details={
                                "artifact_path": artifact_path,
                                "upload_status": artifact["upload_status"],
                            },
                        )
                    repo.increment_upload_attempt(session_id, artifact_path)
                    upload_targets.append(self._build_upload_target(artifact))

                repo.set_session_ingest_status(session_id, "uploading")
                repo.insert_audit_log(
                    session_id=session_id,
                    action_type="presign_artifacts",
                    source=None,
                    payload={"artifact_count": len(upload_targets), "artifact_paths": request.artifact_paths},
                )

        return PresignArtifactsResponse(session_id=session_id, upload_targets=upload_targets)

    def complete_artifacts(
        self,
        session_id: str,
        request: CompleteArtifactsRequest,
        idempotency_key: str | None,
        raw_body: bytes,
    ) -> CompleteArtifactsResponse:
        operation_key = f"complete_artifacts:{session_id}"

        with self._database.connection() as conn:
            with conn.transaction():
                repo = IngestRepository(conn)
                session = repo.get_session(session_id)
                repo.assert_session_can_accept_uploads(session)

                cached = self._maybe_restore_idempotent_response(
                    repo=repo,
                    operation_key=operation_key,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                )
                if cached is not None:
                    return CompleteArtifactsResponse.model_validate(cached)

                for completed in request.completed_artifacts:
                    artifact = repo.get_artifact_by_path(session_id, completed.artifact_path)

                    if completed.artifact_id and str(artifact["artifact_id"]) != completed.artifact_id:
                        raise ValidationError(
                            code="artifact_id_mismatch",
                            message="artifact_id does not match artifact_path",
                            details={
                                "artifact_path": completed.artifact_path,
                                "artifact_id": completed.artifact_id,
                            },
                        )

                    if int(artifact["byte_size"]) != completed.byte_size:
                        repo.mark_artifact_failed(
                            session_id=session_id,
                            artifact_path=completed.artifact_path,
                            code="artifact_size_mismatch",
                            message="Reported byte_size does not match declared artifact size",
                        )
                        raise ValidationError(
                            code="artifact_size_mismatch",
                            message="Reported byte_size does not match declared artifact size",
                            details={"artifact_path": completed.artifact_path},
                        )

                    if artifact["checksum_sha256"] != completed.checksum_sha256:
                        repo.mark_artifact_failed(
                            session_id=session_id,
                            artifact_path=completed.artifact_path,
                            code="artifact_checksum_mismatch",
                            message="Reported checksum does not match manifest checksum",
                        )
                        raise ValidationError(
                            code="artifact_checksum_mismatch",
                            message="Reported checksum does not match manifest checksum",
                            details={"artifact_path": completed.artifact_path},
                        )

                    head = self._storage.head_object(artifact["object_key"])
                    storage_size = int(head.get("ContentLength", -1))
                    if storage_size != completed.byte_size:
                        repo.mark_artifact_failed(
                            session_id=session_id,
                            artifact_path=completed.artifact_path,
                            code="artifact_object_size_mismatch",
                            message="Object storage size does not match completed artifact byte_size",
                        )
                        raise ValidationError(
                            code="artifact_object_size_mismatch",
                            message="Object storage size does not match completed artifact byte_size",
                            details={"artifact_path": completed.artifact_path},
                        )

                    storage_etag = completed.storage_etag or self._clean_etag(head.get("ETag"))
                    repo.mark_artifact_uploaded(
                        session_id=session_id,
                        artifact_path=completed.artifact_path,
                        storage_etag=storage_etag,
                    )

                counts = repo.get_artifact_counts(session_id)
                ingest_status = "uploaded" if counts["pending"] == 0 and counts["failed"] == 0 else "uploading"
                repo.set_session_ingest_status(session_id, ingest_status)
                repo.insert_audit_log(
                    session_id=session_id,
                    action_type="complete_artifacts",
                    source=None,
                    idempotency_key=idempotency_key,
                    payload={
                        "completed_artifact_count": len(request.completed_artifacts),
                        "ingest_status": ingest_status,
                        "uploaded_artifact_count": counts["uploaded"],
                        "pending_artifact_count": counts["pending"],
                        "failed_artifact_count": counts["failed"],
                    },
                )

                response = CompleteArtifactsResponse(
                    session_id=session_id,
                    ingest_status=ingest_status,
                    uploaded_artifact_count=counts["uploaded"],
                    pending_artifact_count=counts["pending"],
                    failed_artifact_count=counts["failed"],
                )

                if idempotency_key:
                    repo.save_idempotency_record(
                        operation_key=operation_key,
                        idempotency_key=idempotency_key,
                        request_body=raw_body,
                        response_payload=response.model_dump(mode="json"),
                        status_code=200,
                        session_id=session_id,
                    )

        return response

    def finalize_session(
        self,
        session_id: str,
        request: FinalizeRawSessionRequest,
        idempotency_key: str | None,
        raw_body: bytes,
    ) -> FinalizeRawSessionResponse:
        operation_key = f"finalize_raw_session:{session_id}"

        with self._database.connection() as conn:
            with conn.transaction():
                repo = IngestRepository(conn)
                repo.get_session(session_id)

                cached = self._maybe_restore_idempotent_response(
                    repo=repo,
                    operation_key=operation_key,
                    idempotency_key=idempotency_key,
                    raw_body=raw_body,
                )
                if cached is not None:
                    return FinalizeRawSessionResponse.model_validate(cached)

                repo.set_session_ingest_status(session_id, "validating")

                missing_required = repo.get_missing_required_artifacts(session_id)
                required_artifacts_ok = len(missing_required) == 0

                stream_manifest_ok = repo.stream_manifest_consistency_ok(session_id)

                checksum_ok = False
                checksum_policy_errors: list[str] = []
                checksum_artifact = repo.get_artifact_by_path(session_id, request.checksum_file_path)
                if checksum_artifact["artifact_role"] != "checksums":
                    checksum_policy_errors.append("checksum_artifact_role_invalid")
                if checksum_artifact["upload_status"] in {"uploaded", "verified"}:
                    checksum_ok = self._validate_artifact_checksum(checksum_artifact)
                else:
                    checksum_policy_errors.append("checksum_artifact_not_uploaded")

                all_artifacts = repo.list_artifacts(session_id)
                all_uploaded_or_verified = all(
                    artifact["upload_status"] in {"uploaded", "verified"} for artifact in all_artifacts
                )
                if not all_uploaded_or_verified:
                    checksum_policy_errors.append("artifacts_not_fully_uploaded")

                object_integrity_errors = 0
                for artifact in repo.list_uploaded_or_verified_artifacts(session_id):
                    try:
                        head = self._storage.head_object(artifact["object_key"])
                        storage_size = int(head.get("ContentLength", -1))
                        if storage_size != int(artifact["byte_size"]):
                            object_integrity_errors += 1
                            repo.mark_artifact_failed(
                                session_id=session_id,
                                artifact_path=artifact["artifact_path"],
                                code="artifact_object_size_mismatch",
                                message="Object storage size does not match expected artifact size",
                            )
                            continue

                        repo.mark_artifact_verified(session_id, artifact["artifact_path"])
                    except ConflictError:
                        object_integrity_errors += 1
                        repo.mark_artifact_failed(
                            session_id=session_id,
                            artifact_path=artifact["artifact_path"],
                            code="artifact_object_missing",
                            message="Artifact object is missing in object storage",
                        )

                if checksum_ok:
                    try:
                        checksum_entries = self._parse_sha256sums(
                            self._storage.read_object(checksum_artifact["object_key"])
                        )
                        checksum_errors = self._validate_checksum_policy(
                            checksum_entries=checksum_entries,
                            artifacts=all_artifacts,
                            checksum_file_path=request.checksum_file_path,
                            package_checksum_sha256=request.package_checksum_sha256,
                        )
                        checksum_policy_errors.extend(checksum_errors)
                    except ValidationError as exc:
                        checksum_policy_errors.append(exc.code)

                error_count = 0
                if not required_artifacts_ok:
                    error_count += len(missing_required)
                if not stream_manifest_ok:
                    error_count += 1
                if not checksum_ok:
                    error_count += 1
                error_count += len(checksum_policy_errors)
                error_count += object_integrity_errors

                validation_summary = ValidationSummary(
                    required_artifacts_ok=required_artifacts_ok and object_integrity_errors == 0 and all_uploaded_or_verified,
                    checksum_ok=checksum_ok and len(checksum_policy_errors) == 0,
                    stream_manifest_ok=stream_manifest_ok,
                    warning_count=0,
                    error_count=error_count,
                )

                ingest_status = "ingested" if validation_summary.error_count == 0 else "failed"
                last_error_code = None
                last_error_message = None
                if ingest_status == "failed":
                    last_error_code = "finalize_validation_failed"
                    last_error_message = "Finalize checks failed"

                finalized_at_utc = repo.set_session_finalize_result(
                    session_id=session_id,
                    ingest_status=ingest_status,
                    checksum_file_path=request.checksum_file_path,
                    package_checksum_sha256=request.package_checksum_sha256,
                    last_error_code=last_error_code,
                    last_error_message=last_error_message,
                )

                repo.insert_audit_log(
                    session_id=session_id,
                    action_type="finalize_ingest",
                    source=None,
                    idempotency_key=idempotency_key,
                    payload={
                        "ingest_status": ingest_status,
                        "validation_summary": validation_summary.model_dump(mode="json"),
                        "missing_required_artifacts": missing_required,
                        "checksum_policy_errors": checksum_policy_errors,
                    },
                )

                response = FinalizeRawSessionResponse(
                    session_id=session_id,
                    ingest_status=ingest_status,
                    finalized_at_utc=finalized_at_utc,
                    validation_summary=validation_summary,
                )

                if idempotency_key:
                    repo.save_idempotency_record(
                        operation_key=operation_key,
                        idempotency_key=idempotency_key,
                        request_body=raw_body,
                        response_payload=response.model_dump(mode="json"),
                        status_code=200,
                        session_id=session_id,
                    )

        return response

    def _build_upload_targets(self, artifacts: list[dict[str, Any]]) -> list[ArtifactUploadTarget]:
        return [self._build_upload_target(artifact) for artifact in artifacts]

    def _build_upload_target(self, artifact: dict[str, Any]) -> ArtifactUploadTarget:
        upload_url, expires_at, required_headers = self._storage.create_put_target(
            object_key=artifact["object_key"],
            content_type=artifact["content_type"],
        )
        return ArtifactUploadTarget(
            artifact_id=str(artifact["artifact_id"]),
            artifact_path=artifact["artifact_path"],
            artifact_role=artifact["artifact_role"],
            object_key=artifact["object_key"],
            upload_method="PUT",
            upload_url=upload_url,
            required_headers=required_headers,
            expires_at_utc=expires_at,
        )

    def _maybe_restore_idempotent_response(
        self,
        repo: IngestRepository,
        operation_key: str,
        idempotency_key: str | None,
        raw_body: bytes,
    ) -> dict[str, Any] | None:
        if not idempotency_key:
            return None

        row = repo.get_idempotency_record(operation_key=operation_key, idempotency_key=idempotency_key)
        if row is None:
            return None

        return repo.assert_idempotency_match(row=row, request_body=raw_body)

    @staticmethod
    def _clean_etag(etag: str | None) -> str | None:
        if etag is None:
            return None
        return etag.strip('"')

    def _validate_artifact_checksum(self, artifact: dict[str, Any]) -> bool:
        content = self._storage.read_object(artifact["object_key"])
        return sha256(content).hexdigest() == artifact["checksum_sha256"]

    @staticmethod
    def _parse_sha256sums(content: bytes) -> dict[str, str]:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(
                code="checksum_file_invalid_encoding",
                message="Checksum file must be UTF-8 text",
            ) from exc

        result: dict[str, str] = {}
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                raise ValidationError(
                    code="checksum_file_invalid_line",
                    message="Each checksum line must contain '<sha256> <path>'",
                    details={"line": line_number},
                )

            checksum, artifact_path = parts[0], parts[1].strip()
            if not SHA256_HEX_RE.fullmatch(checksum):
                raise ValidationError(
                    code="checksum_file_invalid_hash",
                    message="Checksum hash must be 64 lowercase hex characters",
                    details={"line": line_number},
                )
            if not artifact_path or artifact_path.startswith("/") or "\\" in artifact_path:
                raise ValidationError(
                    code="checksum_file_invalid_path",
                    message="Checksum artifact path must be a relative POSIX path",
                    details={"line": line_number},
                )
            if ".." in artifact_path.split("/"):
                raise ValidationError(
                    code="checksum_file_invalid_path",
                    message="Checksum artifact path cannot contain '..' segments",
                    details={"line": line_number},
                )
            if artifact_path in result:
                raise ValidationError(
                    code="checksum_file_duplicate_path",
                    message="Checksum artifact path must be unique",
                    details={"line": line_number, "artifact_path": artifact_path},
                )

            result[artifact_path] = checksum

        return result

    @staticmethod
    def _validate_checksum_policy(
        checksum_entries: dict[str, str],
        artifacts: list[dict[str, Any]],
        checksum_file_path: str,
        package_checksum_sha256: str,
    ) -> list[str]:
        errors: list[str] = []
        artifacts_by_path = {artifact["artifact_path"]: artifact for artifact in artifacts}

        checksum_artifact = artifacts_by_path.get(checksum_file_path)
        if checksum_artifact is None:
            return ["checksum_artifact_missing"]

        if checksum_artifact["checksum_sha256"] != package_checksum_sha256:
            errors.append("package_checksum_mismatch")

        expected_paths = {
            artifact["artifact_path"]
            for artifact in artifacts
            if artifact["artifact_path"] != checksum_file_path and not artifact["artifact_path"].startswith("checksums/")
        }
        listed_paths = set(checksum_entries.keys())

        if expected_paths - listed_paths:
            errors.append("checksum_manifest_missing_paths")
        if listed_paths - expected_paths:
            errors.append("checksum_manifest_unexpected_paths")

        for path, expected_hash in checksum_entries.items():
            artifact = artifacts_by_path.get(path)
            if artifact is None:
                continue
            if artifact["checksum_sha256"] != expected_hash:
                errors.append("checksum_manifest_hash_mismatch")
                break

        return errors
