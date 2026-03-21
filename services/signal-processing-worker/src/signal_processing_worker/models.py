from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

IngestStatus = Literal["accepted", "uploading", "uploaded", "validating", "ingested", "failed", "cancelled"]
QualityStatus = Literal["pass", "warning", "fail"]


class OffsetInterval(BaseModel):
    started_offset_ms: int = Field(ge=0)
    ended_offset_ms: int = Field(ge=0)
    reason: str

    @model_validator(mode="after")
    def validate_order(self) -> "OffsetInterval":
        if self.ended_offset_ms < self.started_offset_ms:
            raise ValueError("ended_offset_ms must be >= started_offset_ms")
        return self


class RawStreamDescriptor(BaseModel):
    stream_id: str
    device_id: str
    stream_name: StreamName
    stream_kind: str
    sample_count: int = Field(ge=0)
    file_ref: str
    sample_object_key: str | None = None
    sample_upload_status: str | None = None
    missing_intervals: list[dict[str, Any]] = Field(default_factory=list)
    available_for_processing: bool = True
    unavailability_reason: str | None = None


class RawSample(BaseModel):
    sample_index: int | None = None
    offset_ms: int = Field(ge=0)
    timestamp_utc: datetime | None = None
    values: dict[str, Any] = Field(default_factory=dict)


class CleanSample(BaseModel):
    sample_index: int | None = None
    raw_offset_ms: int = Field(ge=0)
    aligned_offset_ms: int = Field(ge=0)
    timestamp_utc: datetime | None = None
    aligned_timestamp_utc: datetime
    values: dict[str, Any] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)


class StreamQualitySummary(BaseModel):
    expected_interval_ms: int | None = Field(default=None, ge=1)
    raw_sample_count: int = Field(default=0, ge=0)
    clean_sample_count: int = Field(default=0, ge=0)
    dropped_sample_count: int = Field(default=0, ge=0)
    gap_count: int = Field(default=0, ge=0)
    total_gap_duration_ms: int = Field(default=0, ge=0)
    packet_loss_estimated_samples: int = Field(default=0, ge=0)
    motion_artifact_count: int = Field(default=0, ge=0)
    noisy_sample_count: int = Field(default=0, ge=0)
    gap_intervals: list[OffsetInterval] = Field(default_factory=list)
    motion_artifact_intervals: list[OffsetInterval] = Field(default_factory=list)
    noisy_intervals: list[OffsetInterval] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProcessedStream(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream_name: StreamName
    stream_id: str
    device_id: str
    raw_sample_count: int = Field(ge=0)
    clean_sample_count: int = Field(ge=0)
    alignment_delta_ms: int
    quality: StreamQualitySummary
    clean_samples: list[CleanSample] = Field(default_factory=list, exclude=True)
    clean_samples_object_key: str | None = None
    quality_report_object_key: str | None = None
    warnings: list[str] = Field(default_factory=list)


class QualityCheck(BaseModel):
    check_id: str
    status: QualityStatus
    message: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class PreprocessingRunResult(BaseModel):
    preprocessing_version: str
    session_id: str
    status: Literal["completed", "failed"]
    overall_quality_status: QualityStatus
    source_ingest_status: IngestStatus
    started_at_utc: datetime
    ended_at_utc: datetime
    generated_at_utc: datetime
    processed_stream_count: int = Field(ge=0)
    skipped_stream_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    streams: list[ProcessedStream] = Field(default_factory=list)
    summary_object_key: str | None = None
