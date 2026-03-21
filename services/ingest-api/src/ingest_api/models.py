from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHA256_PATTERN = r"^[0-9a-f]{64}$"

IngestStatus = Literal["accepted", "uploading", "uploaded", "validating", "ingested", "failed", "cancelled"]
SessionStatus = Literal["completed", "partial", "failed", "exported"]
StreamName = Literal[
    "polar_ecg",
    "polar_rr",
    "polar_hr",
    "polar_acc",
    "watch_heart_rate",
    "watch_accelerometer",
    "watch_gyroscope",
    "watch_activity_context",
    "watch_hrv",
]
ArtifactRole = Literal[
    "manifest_session",
    "manifest_subject",
    "manifest_devices",
    "manifest_streams",
    "manifest_segments",
    "stream_metadata",
    "stream_samples",
    "session_events",
    "self_report",
    "quality_report",
    "checksums",
    "other",
]


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_type: Literal["device", "operator", "service"] | None = None
    actor_id: str | None = None
    client_version: str | None = None


class SessionManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=3, max_length=128)
    subject_id: str = Field(min_length=3, max_length=128)
    schema_version: str = Field(min_length=1, max_length=64)
    protocol_version: str = Field(min_length=1, max_length=64)
    session_type: str = Field(min_length=1, max_length=64)
    status: SessionStatus
    started_at_utc: datetime
    ended_at_utc: datetime
    timezone: str = Field(min_length=1, max_length=64)
    coordinator_device_id: str | None = Field(default=None, max_length=128)
    capture_app_version: str = Field(max_length=64)
    operator_mode: str | None = Field(default=None, max_length=64)
    session_environment: dict[str, str] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=4000)
    planned_segment_count: int | None = Field(default=None, ge=0)
    observed_segment_count: int | None = Field(default=None, ge=0)
    stream_count: int | None = Field(default=None, ge=0)
    export_completed_at_utc: datetime | None = None

    @model_validator(mode="after")
    def validate_time_order(self) -> "SessionManifestInput":
        if self.ended_at_utc < self.started_at_utc:
            raise ValueError("session.ended_at_utc must be >= session.started_at_utc")
        return self


class SubjectManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=3, max_length=128)
    cohort: str | None = Field(default=None, max_length=64)
    study_group: str | None = Field(default=None, max_length=64)
    sex: str | None = Field(default=None, max_length=32)
    age_range: str | None = Field(default=None, max_length=32)
    consent_version: str = Field(max_length=64)
    baseline_notes: str | None = Field(default=None, max_length=4000)


class DeviceManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=3, max_length=128)
    device_role: Literal["coordinator_phone", "polar_h10", "apple_watch"]
    manufacturer: str = Field(max_length=64)
    model: str = Field(max_length=64)
    firmware_version: str | None = Field(default=None, max_length=64)
    source_name: str = Field(max_length=128)
    connection_started_at_utc: datetime | None = None
    connection_ended_at_utc: datetime | None = None


class SegmentManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=3, max_length=128)
    name: str = Field(max_length=64)
    order_index: int = Field(ge=0)
    started_at_utc: datetime
    ended_at_utc: datetime
    planned: bool
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_time_order(self) -> "SegmentManifestInput":
        if self.ended_at_utc < self.started_at_utc:
            raise ValueError("segment.ended_at_utc must be >= segment.started_at_utc")
        return self


class MissingInterval(BaseModel):
    started_at_utc: datetime
    ended_at_utc: datetime


class StreamManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream_id: str = Field(min_length=3, max_length=128)
    device_id: str = Field(min_length=3, max_length=128)
    stream_name: StreamName
    stream_kind: str = Field(max_length=64)
    unit_schema: dict[str, Any] = Field(default_factory=dict)
    sample_count: int = Field(ge=0)
    started_at_utc: datetime | None = None
    ended_at_utc: datetime | None = None
    file_ref: str = Field(min_length=3, max_length=1024)
    checksum_sha256: str = Field(pattern=SHA256_PATTERN)
    missing_intervals: list[MissingInterval] = Field(default_factory=list)


class ArtifactDescriptorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_path: str = Field(min_length=3, max_length=1024)
    artifact_role: ArtifactRole
    stream_name: StreamName | None = None
    content_type: str = Field(max_length=128)
    byte_size: int = Field(ge=0)
    checksum_sha256: str = Field(pattern=SHA256_PATTERN)


class CompletedArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str | None = None
    artifact_path: str = Field(min_length=3, max_length=1024)
    storage_etag: str | None = Field(default=None, max_length=128)
    byte_size: int = Field(ge=0)
    checksum_sha256: str = Field(pattern=SHA256_PATTERN)


class ArtifactUploadTarget(BaseModel):
    artifact_id: str
    artifact_path: str
    artifact_role: str
    object_key: str
    upload_method: Literal["PUT"] = "PUT"
    upload_url: str
    required_headers: dict[str, str] = Field(default_factory=dict)
    expires_at_utc: datetime


class ValidationSummary(BaseModel):
    required_artifacts_ok: bool
    checksum_ok: bool
    stream_manifest_ok: bool
    warning_count: int = Field(ge=0)
    error_count: int = Field(ge=0)


class IngestError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class CreateRawSessionIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: SessionManifestInput
    subject: SubjectManifestInput
    devices: list[DeviceManifestInput] = Field(min_length=1)
    segments: list[SegmentManifestInput] = Field(min_length=1)
    streams: list[StreamManifestInput] = Field(min_length=1)
    artifacts: list[ArtifactDescriptorInput] = Field(min_length=1)
    source: SourceInfo | None = None

    @model_validator(mode="after")
    def validate_cross_refs(self) -> "CreateRawSessionIngestRequest":
        if self.session.subject_id != self.subject.subject_id:
            raise ValueError("session.subject_id must match subject.subject_id")

        known_devices = {device.device_id for device in self.devices}
        if len(known_devices) != len(self.devices):
            raise ValueError("device_id values must be unique within session")

        stream_ids = {stream.stream_id for stream in self.streams}
        if len(stream_ids) != len(self.streams):
            raise ValueError("stream_id values must be unique within session")

        stream_names = {stream.stream_name for stream in self.streams}
        if len(stream_names) != len(self.streams):
            raise ValueError("stream_name values must be unique within session")

        for stream in self.streams:
            if stream.device_id not in known_devices:
                raise ValueError(f"stream.device_id not found in devices: {stream.device_id}")

        artifact_paths = {artifact.artifact_path for artifact in self.artifacts}
        if len(artifact_paths) != len(self.artifacts):
            raise ValueError("artifact_path values must be unique")

        for stream in self.streams:
            if stream.file_ref not in artifact_paths:
                raise ValueError(f"stream.file_ref not found in artifacts: {stream.file_ref}")

        return self


class CreateRawSessionIngestResponse(BaseModel):
    session_id: str
    ingest_status: IngestStatus
    created_at_utc: datetime
    expected_artifact_count: int = Field(ge=1)
    upload_targets: list[ArtifactUploadTarget]
    warnings: list[str] = Field(default_factory=list)


class PresignArtifactsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_paths: list[str] = Field(min_length=1)


class PresignArtifactsResponse(BaseModel):
    session_id: str
    upload_targets: list[ArtifactUploadTarget]


class CompleteArtifactsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_artifacts: list[CompletedArtifactInput] = Field(min_length=1)


class CompleteArtifactsResponse(BaseModel):
    session_id: str
    ingest_status: IngestStatus
    uploaded_artifact_count: int = Field(ge=0)
    pending_artifact_count: int = Field(ge=0)
    failed_artifact_count: int = Field(ge=0)


class FinalizeClientObserved(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uploaded_artifact_count: int | None = Field(default=None, ge=0)
    stream_count: int | None = Field(default=None, ge=0)
    event_count: int | None = Field(default=None, ge=0)


class FinalizeRawSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_checksum_sha256: str = Field(pattern=SHA256_PATTERN)
    checksum_file_path: str = Field(min_length=3, max_length=1024)
    client_observed: FinalizeClientObserved | None = None


class FinalizeRawSessionResponse(BaseModel):
    session_id: str
    ingest_status: IngestStatus
    finalized_at_utc: datetime
    validation_summary: ValidationSummary


class RawSessionIngestState(BaseModel):
    session_id: str
    subject_id: str
    session_status: SessionStatus
    ingest_status: IngestStatus
    schema_version: str | None = None
    protocol_version: str | None = None
    storage_root_prefix: str | None = None
    checksum_file_path: str | None = None
    package_checksum_sha256: str | None = None
    expected_artifact_count: int = Field(ge=0)
    uploaded_artifact_count: int = Field(ge=0)
    verified_artifact_count: int = Field(ge=0)
    missing_required_artifacts: list[str] = Field(default_factory=list)
    created_at_utc: datetime
    updated_at_utc: datetime
    ingest_finalized_at_utc: datetime | None = None
    ingested_at_utc: datetime | None = None
    last_error: IngestError | None = None
