from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IngestStatus = Literal["accepted", "uploading", "uploaded", "validating", "ingested", "failed", "cancelled"]
ReplayMode = Literal["realtime", "accelerated"]
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


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload


class ReplaySegment(BaseModel):
    segment_id: str
    name: str
    order_index: int = Field(ge=0)
    started_at_utc: datetime
    ended_at_utc: datetime
    planned: bool
    notes: str | None = None


class ReplayStreamDescriptor(BaseModel):
    stream_id: str
    device_id: str
    stream_name: StreamName
    stream_kind: str
    sample_count: int = Field(ge=0)
    started_at_utc: datetime | None = None
    ended_at_utc: datetime | None = None
    file_ref: str
    sample_object_key: str | None = None
    sample_content_type: str | None = None
    sample_upload_status: str | None = None
    checksum_sha256: str
    metadata_artifact_path: str | None = None
    metadata_object_key: str | None = None
    available_for_replay: bool
    unavailability_reason: str | None = None


class ReplayManifestResponse(BaseModel):
    replay_manifest_version: str = "1.0.0"
    session_id: str
    subject_id: str
    ingest_status: IngestStatus
    storage_root_prefix: str
    started_at_utc: datetime
    ended_at_utc: datetime
    timezone: str
    duration_ms: int = Field(ge=0)
    stream_count: int = Field(ge=0)
    segments: list[ReplaySegment]
    streams: list[ReplayStreamDescriptor]
    warnings: list[str] = Field(default_factory=list)


class ReplayWindowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ReplayMode = "realtime"
    speed_multiplier: float = Field(default=1.0, gt=0.0, le=200.0)
    from_offset_ms: int = Field(default=0, ge=0)
    window_ms: int = Field(default=5000, ge=100, le=600000)
    stream_names: list[StreamName] | None = None
    include_events: bool = True
    max_samples_per_stream: int = Field(default=2000, ge=1, le=100000)

    @model_validator(mode="after")
    def validate_params(self) -> "ReplayWindowRequest":
        if self.mode == "realtime" and self.speed_multiplier != 1.0:
            raise ValueError("speed_multiplier must be 1.0 for realtime mode")

        if self.stream_names is not None and len(set(self.stream_names)) != len(self.stream_names):
            raise ValueError("stream_names values must be unique")

        return self


class ReplaySample(BaseModel):
    stream_name: StreamName
    stream_id: str
    device_id: str
    sample_index: int | None = None
    offset_ms: int = Field(ge=0)
    timestamp_utc: datetime | None = None
    replay_at_offset_ms: int = Field(ge=0)
    values: dict[str, Any] = Field(default_factory=dict)


class ReplayEvent(BaseModel):
    event_id: str
    event_type: str
    source: str
    occurred_at_utc: datetime
    offset_ms: int = Field(ge=0)
    replay_at_offset_ms: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


class ReplayWindowResponse(BaseModel):
    session_id: str
    mode: ReplayMode
    speed_multiplier: float = Field(gt=0.0)
    from_offset_ms: int = Field(ge=0)
    to_offset_ms: int = Field(ge=0)
    next_offset_ms: int = Field(ge=0)
    stream_names: list[StreamName]
    sample_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    samples: list[ReplaySample]
    events: list[ReplayEvent]
    warnings: list[str] = Field(default_factory=list)
