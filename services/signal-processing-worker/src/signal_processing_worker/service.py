from __future__ import annotations

import csv
import math
import re
from datetime import datetime, timedelta, timezone
from io import StringIO
from statistics import median
from typing import Any, Iterable

from signal_processing_worker.db import Database
from signal_processing_worker.errors import ConflictError, ValidationError
from signal_processing_worker.models import (
    CleanSample,
    OffsetInterval,
    PreprocessingRunResult,
    ProcessedStream,
    QualityCheck,
    QualityStatus,
    RawSample,
    RawStreamDescriptor,
    StreamQualitySummary,
    StreamName,
)
from signal_processing_worker.repository import ProcessingRepository
from signal_processing_worker.storage import S3Storage

READY_INGEST_STATUSES = {"ingested", "uploaded", "validating"}
IRREGULAR_STREAMS = {"polar_rr", "watch_activity_context", "watch_hrv"}

DEFAULT_INTERVAL_MS: dict[StreamName, int] = {
    "polar_ecg": 8,
    "polar_rr": 1000,
    "polar_hr": 1000,
    "polar_acc": 20,
    "watch_heart_rate": 5000,
    "watch_accelerometer": 20,
    "watch_gyroscope": 20,
    "watch_activity_context": 10000,
    "watch_hrv": 60000,
}

STREAM_VALUE_LIMITS: dict[StreamName, dict[str, tuple[float, float]]] = {
    "polar_ecg": {"voltage_uv": (-20_000.0, 20_000.0)},
    "polar_rr": {"rr_ms": (250.0, 2_500.0)},
    "polar_hr": {"hr_bpm": (25.0, 240.0)},
    "polar_acc": {
        "acc_x_mg": (-32_000.0, 32_000.0),
        "acc_y_mg": (-32_000.0, 32_000.0),
        "acc_z_mg": (-32_000.0, 32_000.0),
    },
    "watch_heart_rate": {"hr_bpm": (25.0, 240.0), "confidence": (0.0, 1.0)},
    "watch_accelerometer": {
        "acc_x_g": (-16.0, 16.0),
        "acc_y_g": (-16.0, 16.0),
        "acc_z_g": (-16.0, 16.0),
    },
    "watch_gyroscope": {
        "gyro_x_rad_s": (-40.0, 40.0),
        "gyro_y_rad_s": (-40.0, 40.0),
        "gyro_z_rad_s": (-40.0, 40.0),
    },
    "watch_activity_context": {"confidence": (0.0, 1.0)},
    "watch_hrv": {
        "hrv_ms": (5.0, 500.0),
        "sdnn_ms": (5.0, 500.0),
        "rmssd_ms": (5.0, 500.0),
    },
}


class SignalProcessingService:
    def __init__(
        self,
        database: Database,
        storage: S3Storage,
        clean_root_prefix: str,
        preprocessing_version: str,
        gap_factor: float,
        max_samples_per_stream: int,
        persist_outputs: bool,
    ) -> None:
        self._database = database
        self._storage = storage
        self._clean_root_prefix = clean_root_prefix.strip("/")
        self._preprocessing_version = preprocessing_version
        self._gap_factor = max(1.1, gap_factor)
        self._max_samples_per_stream = max(1000, max_samples_per_stream)
        self._persist_outputs = persist_outputs

    def process_session(self, session_id: str, preprocessing_version: str | None = None) -> PreprocessingRunResult:
        pipeline_version = preprocessing_version or self._preprocessing_version
        pipeline_token = self._sanitize_token(pipeline_version)

        with self._database.connection() as conn:
            repo = ProcessingRepository(conn)
            session_row = repo.get_session(session_id)
            stream_rows = repo.list_streams_for_processing(session_id)

        ingest_status = session_row["ingest_status"]
        if ingest_status not in READY_INGEST_STATUSES:
            raise ConflictError(
                code="processing_session_not_ready",
                message="Session is not ready for preprocessing",
                details={"session_id": session_id, "ingest_status": ingest_status},
            )

        if self._persist_outputs:
            self._storage.ensure_clean_bucket()

        warnings: list[str] = []
        streams: list[ProcessedStream] = []

        for row in stream_rows:
            descriptor = self._build_stream_descriptor(row)
            if not descriptor.available_for_processing:
                reason = descriptor.unavailability_reason or "unknown"
                warnings.append(f"stream {descriptor.stream_name} was skipped: {reason}")
                streams.append(
                    ProcessedStream(
                        stream_name=descriptor.stream_name,
                        stream_id=descriptor.stream_id,
                        device_id=descriptor.device_id,
                        raw_sample_count=0,
                        clean_sample_count=0,
                        alignment_delta_ms=0,
                        quality=StreamQualitySummary(
                            raw_sample_count=0,
                            clean_sample_count=0,
                            dropped_sample_count=0,
                            warnings=[reason],
                        ),
                        warnings=[reason],
                    )
                )
                continue

            raw_samples = self._load_raw_samples(descriptor)
            processed_stream = self._process_stream_samples(
                descriptor=descriptor,
                session_started_at_utc=session_row["started_at_utc"],
                raw_samples=raw_samples,
            )

            if self._persist_outputs:
                clean_key = self._build_stream_clean_samples_key(session_id, pipeline_token, descriptor.stream_name)
                quality_key = self._build_stream_quality_key(session_id, pipeline_token, descriptor.stream_name)

                clean_csv = self._render_clean_samples_csv(processed_stream)
                self._storage.write_clean_text(
                    object_key=clean_key,
                    text=clean_csv,
                    content_type="text/csv",
                    gzip_compress=True,
                )
                self._storage.write_clean_json(
                    object_key=quality_key,
                    payload=processed_stream.quality.model_dump(mode="json"),
                )

                processed_stream.clean_samples_object_key = clean_key
                processed_stream.quality_report_object_key = quality_key

            streams.append(processed_stream)

        processed_stream_count = len([stream for stream in streams if stream.raw_sample_count > 0])
        skipped_stream_count = len(streams) - processed_stream_count

        checks = self._build_quality_checks(streams)
        overall_quality_status = self._derive_overall_quality_status(processed_stream_count, checks)

        summary_key = (
            self._build_summary_key(session_id=session_id, pipeline_token=pipeline_token)
            if self._persist_outputs
            else None
        )

        result = PreprocessingRunResult(
            preprocessing_version=pipeline_version,
            session_id=session_id,
            status="completed",
            overall_quality_status=overall_quality_status,
            source_ingest_status=ingest_status,
            started_at_utc=session_row["started_at_utc"],
            ended_at_utc=session_row["ended_at_utc"],
            generated_at_utc=datetime.now(timezone.utc),
            processed_stream_count=processed_stream_count,
            skipped_stream_count=skipped_stream_count,
            warnings=warnings,
            streams=streams,
            summary_object_key=summary_key,
        )

        if self._persist_outputs:
            self._storage.write_clean_json(
                object_key=summary_key,
                payload=result.model_dump(mode="json"),
            )

            notes = "; ".join(warnings)[:4000] if warnings else None
            with self._database.connection() as conn:
                with conn.transaction():
                    repo = ProcessingRepository(conn)
                    repo.upsert_quality_report(
                        session_id=session_id,
                        quality_report_id=f"preprocessing_{pipeline_token}",
                        generated_at_utc=result.generated_at_utc,
                        overall_status=result.overall_quality_status,
                        checks=[check.model_dump(mode="json") for check in checks],
                        notes=notes,
                        metadata={
                            "preprocessing_version": pipeline_version,
                            "summary_object_key": summary_key,
                            "processed_stream_count": processed_stream_count,
                            "skipped_stream_count": skipped_stream_count,
                            "generated_by": "signal-processing-worker",
                        },
                    )

        return result

    def _build_stream_descriptor(self, row: dict[str, Any]) -> RawStreamDescriptor:
        upload_status = row.get("sample_upload_status")
        sample_object_key = row.get("sample_object_key")

        available = sample_object_key is not None and upload_status in {"uploaded", "verified"}
        unavailable_reason = None
        if not available:
            if sample_object_key is None:
                unavailable_reason = "sample artifact object_key is missing"
            elif upload_status is None:
                unavailable_reason = "sample artifact row is missing"
            else:
                unavailable_reason = f"sample artifact upload_status is {upload_status}"

        return RawStreamDescriptor(
            stream_id=row["stream_id"],
            device_id=row["device_id"],
            stream_name=row["stream_name"],
            stream_kind=row["stream_kind"],
            sample_count=row["sample_count"],
            file_ref=row["file_ref"],
            sample_object_key=sample_object_key,
            sample_upload_status=upload_status,
            missing_intervals=row.get("missing_intervals") or [],
            available_for_processing=available,
            unavailability_reason=unavailable_reason,
        )

    def _load_raw_samples(self, descriptor: RawStreamDescriptor) -> list[RawSample]:
        if not descriptor.sample_object_key:
            raise ValidationError(
                code="processing_missing_object_key",
                message="Stream has no sample object key",
                details={"stream_name": descriptor.stream_name},
            )

        text_payload = self._storage.read_raw_text(descriptor.sample_object_key)
        reader = csv.DictReader(StringIO(text_payload))
        if not reader.fieldnames:
            return []

        if "offset_ms" not in reader.fieldnames:
            raise ValidationError(
                code="processing_missing_offset_ms",
                message="Stream sample file has no offset_ms column",
                details={"stream_name": descriptor.stream_name, "object_key": descriptor.sample_object_key},
            )

        raw_samples: list[RawSample] = []
        for row in reader:
            if len(raw_samples) >= self._max_samples_per_stream:
                raise ValidationError(
                    code="processing_too_many_samples",
                    message="Raw stream exceeded configured sample limit",
                    details={
                        "stream_name": descriptor.stream_name,
                        "max_samples_per_stream": self._max_samples_per_stream,
                    },
                )

            offset_ms = self._parse_int(row.get("offset_ms"))
            if offset_ms is None or offset_ms < 0:
                continue

            values: dict[str, Any] = {}
            for key, value in row.items():
                if key in {"sample_index", "offset_ms", "timestamp_utc", "source_timestamp", "ingested_at_utc"}:
                    continue
                values[key] = self._coerce_csv_value(value)

            raw_samples.append(
                RawSample(
                    sample_index=self._parse_int(row.get("sample_index")),
                    offset_ms=offset_ms,
                    timestamp_utc=self._parse_datetime(row.get("timestamp_utc")),
                    values=values,
                )
            )

        return raw_samples

    def _process_stream_samples(
        self,
        descriptor: RawStreamDescriptor,
        session_started_at_utc: datetime,
        raw_samples: list[RawSample],
    ) -> ProcessedStream:
        alignment_delta_ms = self._estimate_alignment_delta_ms(session_started_at_utc, raw_samples)

        aligned_offsets_raw: list[int] = []
        clean_samples: list[CleanSample] = []
        noisy_intervals: list[OffsetInterval] = []
        quality_warnings: list[str] = []

        for sample in raw_samples:
            aligned_offset_ms = max(0, sample.offset_ms - alignment_delta_ms)
            aligned_offsets_raw.append(aligned_offset_ms)
            aligned_timestamp_utc = session_started_at_utc + timedelta(milliseconds=aligned_offset_ms)

            clean_values, noisy_reason = self._sanitize_values(descriptor.stream_name, sample.values)
            if noisy_reason is not None:
                noisy_intervals.append(
                    OffsetInterval(
                        started_offset_ms=aligned_offset_ms,
                        ended_offset_ms=aligned_offset_ms,
                        reason=noisy_reason,
                    )
                )
                continue

            clean_samples.append(
                CleanSample(
                    sample_index=sample.sample_index,
                    raw_offset_ms=sample.offset_ms,
                    aligned_offset_ms=aligned_offset_ms,
                    timestamp_utc=sample.timestamp_utc,
                    aligned_timestamp_utc=aligned_timestamp_utc,
                    values=clean_values,
                    quality_flags=[],
                )
            )

        expected_interval_ms, gap_intervals, total_gap_duration_ms, packet_loss = self._detect_gaps(
            aligned_offsets=aligned_offsets_raw,
            stream_name=descriptor.stream_name,
        )

        motion_intervals = self._mark_motion_artifacts(
            clean_samples=clean_samples,
            stream_name=descriptor.stream_name,
        )

        if raw_samples and not clean_samples:
            quality_warnings.append("all samples were dropped during cleaning")

        quality = StreamQualitySummary(
            expected_interval_ms=expected_interval_ms,
            raw_sample_count=len(raw_samples),
            clean_sample_count=len(clean_samples),
            dropped_sample_count=max(0, len(raw_samples) - len(clean_samples)),
            gap_count=len(gap_intervals),
            total_gap_duration_ms=total_gap_duration_ms,
            packet_loss_estimated_samples=packet_loss,
            motion_artifact_count=len(motion_intervals),
            noisy_sample_count=len(noisy_intervals),
            gap_intervals=gap_intervals,
            motion_artifact_intervals=motion_intervals,
            noisy_intervals=noisy_intervals,
            warnings=quality_warnings,
        )

        return ProcessedStream(
            stream_name=descriptor.stream_name,
            stream_id=descriptor.stream_id,
            device_id=descriptor.device_id,
            raw_sample_count=len(raw_samples),
            clean_sample_count=len(clean_samples),
            alignment_delta_ms=alignment_delta_ms,
            quality=quality,
            clean_samples=clean_samples,
            warnings=quality_warnings,
        )

    def _sanitize_values(self, stream_name: StreamName, values: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        limits = STREAM_VALUE_LIMITS.get(stream_name, {})
        output: dict[str, Any] = {}

        for key, value in values.items():
            if isinstance(value, float) and not math.isfinite(value):
                return {}, f"{key}_not_finite"

            if key in limits and value is not None:
                numeric = self._as_float(value)
                if numeric is None:
                    return {}, f"{key}_not_numeric"

                lower, upper = limits[key]
                if numeric < lower or numeric > upper:
                    return {}, f"{key}_out_of_range"

            output[key] = value

        return output, None

    def _estimate_alignment_delta_ms(self, session_started_at_utc: datetime, raw_samples: list[RawSample]) -> int:
        deltas: list[int] = []

        for sample in raw_samples:
            if sample.timestamp_utc is None:
                continue
            observed_offset = self._duration_ms(session_started_at_utc, sample.timestamp_utc)
            deltas.append(sample.offset_ms - observed_offset)

        if len(deltas) < 3:
            return 0

        return int(round(median(deltas)))

    def _detect_gaps(
        self,
        aligned_offsets: list[int],
        stream_name: StreamName,
    ) -> tuple[int | None, list[OffsetInterval], int, int]:
        if len(aligned_offsets) < 2:
            return None, [], 0, 0

        deltas: list[int] = []
        for previous, current in zip(aligned_offsets, aligned_offsets[1:]):
            delta = current - previous
            if delta > 0:
                deltas.append(delta)

        if not deltas:
            return None, [], 0, 0

        expected_interval_ms = self._estimate_expected_interval_ms(stream_name, deltas)
        if expected_interval_ms is None or expected_interval_ms <= 0:
            return None, [], 0, 0

        threshold = max(int(expected_interval_ms * self._gap_factor), expected_interval_ms + 1)
        gap_intervals: list[OffsetInterval] = []
        total_gap_duration_ms = 0
        packet_loss = 0

        for previous, current in zip(aligned_offsets, aligned_offsets[1:]):
            delta = current - previous
            if delta <= threshold:
                continue

            gap_duration_ms = max(0, delta - expected_interval_ms)
            estimated_missing = max(0, int(round(delta / expected_interval_ms)) - 1)

            gap_intervals.append(
                OffsetInterval(
                    started_offset_ms=previous,
                    ended_offset_ms=current,
                    reason="gap_detected",
                )
            )
            total_gap_duration_ms += gap_duration_ms
            packet_loss += estimated_missing

        return expected_interval_ms, gap_intervals, total_gap_duration_ms, packet_loss

    def _estimate_expected_interval_ms(self, stream_name: StreamName, deltas: list[int]) -> int | None:
        default_interval = DEFAULT_INTERVAL_MS.get(stream_name)

        positive_deltas = [delta for delta in deltas if delta > 0]
        if not positive_deltas:
            return default_interval

        median_delta = int(round(median(positive_deltas)))

        if len(positive_deltas) < 3 and default_interval is not None:
            if stream_name in IRREGULAR_STREAMS:
                return max(default_interval, median_delta)
            return default_interval

        if stream_name in IRREGULAR_STREAMS:
            if default_interval is None:
                return median_delta if median_delta > 0 else None
            return max(default_interval, median_delta)

        if median_delta > 0:
            return median_delta

        return default_interval

    def _mark_motion_artifacts(self, clean_samples: list[CleanSample], stream_name: StreamName) -> list[OffsetInterval]:
        intervals: list[OffsetInterval] = []

        if stream_name in {"polar_hr", "watch_heart_rate"}:
            previous_hr: float | None = None
            previous_offset: int | None = None
            for sample in clean_samples:
                hr_value = self._extract_numeric(sample.values, ("hr_bpm",))
                if hr_value is None:
                    continue

                if previous_hr is not None and previous_offset is not None:
                    offset_delta = sample.aligned_offset_ms - previous_offset
                    if 0 < offset_delta <= 2000 and abs(hr_value - previous_hr) >= 25.0:
                        sample.quality_flags.append("motion_artifact")
                        intervals.append(
                            OffsetInterval(
                                started_offset_ms=previous_offset,
                                ended_offset_ms=sample.aligned_offset_ms,
                                reason="heart_rate_jump",
                            )
                        )

                previous_hr = hr_value
                previous_offset = sample.aligned_offset_ms

            return intervals

        if stream_name in {"polar_acc", "watch_accelerometer"}:
            if stream_name == "polar_acc":
                axis = ("acc_x_mg", "acc_y_mg", "acc_z_mg")
                threshold = 2500.0
                reason = "high_acceleration_mg"
            else:
                axis = ("acc_x_g", "acc_y_g", "acc_z_g")
                threshold = 2.5
                reason = "high_acceleration_g"

            for sample in clean_samples:
                magnitude = self._extract_vector_magnitude(sample.values, axis)
                if magnitude is None or magnitude <= threshold:
                    continue
                sample.quality_flags.append("motion_artifact")
                intervals.append(
                    OffsetInterval(
                        started_offset_ms=sample.aligned_offset_ms,
                        ended_offset_ms=sample.aligned_offset_ms,
                        reason=reason,
                    )
                )

            return intervals

        if stream_name == "watch_gyroscope":
            axis = ("gyro_x_rad_s", "gyro_y_rad_s", "gyro_z_rad_s")
            for sample in clean_samples:
                magnitude = self._extract_vector_magnitude(sample.values, axis)
                if magnitude is None or magnitude <= 15.0:
                    continue
                sample.quality_flags.append("motion_artifact")
                intervals.append(
                    OffsetInterval(
                        started_offset_ms=sample.aligned_offset_ms,
                        ended_offset_ms=sample.aligned_offset_ms,
                        reason="high_angular_velocity",
                    )
                )

        return intervals

    def _build_quality_checks(self, streams: list[ProcessedStream]) -> list[QualityCheck]:
        checks: list[QualityCheck] = []

        for stream in streams:
            status: QualityStatus = "pass"
            message = "stream passed preprocessing quality checks"

            if stream.raw_sample_count == 0:
                status = "warning"
                message = "stream has no processable samples"
            elif (
                stream.quality.gap_count > 0
                or stream.quality.packet_loss_estimated_samples > 0
                or stream.quality.motion_artifact_count > 0
                or stream.quality.noisy_sample_count > 0
                or bool(stream.warnings)
            ):
                status = "warning"
                message = "stream has quality warnings"

            checks.append(
                QualityCheck(
                    check_id=f"stream.{stream.stream_name}.quality",
                    status=status,
                    message=message,
                    metrics={
                        "raw_sample_count": stream.raw_sample_count,
                        "clean_sample_count": stream.clean_sample_count,
                        "alignment_delta_ms": stream.alignment_delta_ms,
                        "gap_count": stream.quality.gap_count,
                        "packet_loss_estimated_samples": stream.quality.packet_loss_estimated_samples,
                        "motion_artifact_count": stream.quality.motion_artifact_count,
                        "noisy_sample_count": stream.quality.noisy_sample_count,
                    },
                )
            )

        return checks

    @staticmethod
    def _derive_overall_quality_status(processed_stream_count: int, checks: list[QualityCheck]) -> QualityStatus:
        if processed_stream_count == 0:
            return "fail"

        if any(check.status == "fail" for check in checks):
            return "fail"

        if any(check.status == "warning" for check in checks):
            return "warning"

        return "pass"

    def _render_clean_samples_csv(self, processed_stream: ProcessedStream) -> str:
        clean_samples = processed_stream.clean_samples

        value_keys: set[str] = set()
        for sample in clean_samples:
            value_keys.update(sample.values.keys())

        fieldnames = [
            "sample_index",
            "raw_offset_ms",
            "aligned_offset_ms",
            "timestamp_utc",
            "aligned_timestamp_utc",
            "quality_flags",
            *sorted(value_keys),
        ]

        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()

        for sample in clean_samples:
            row: dict[str, Any] = {
                "sample_index": sample.sample_index,
                "raw_offset_ms": sample.raw_offset_ms,
                "aligned_offset_ms": sample.aligned_offset_ms,
                "timestamp_utc": self._format_datetime(sample.timestamp_utc),
                "aligned_timestamp_utc": self._format_datetime(sample.aligned_timestamp_utc),
                "quality_flags": "|".join(sample.quality_flags),
            }
            for key in value_keys:
                row[key] = sample.values.get(key)
            writer.writerow(row)

        return buffer.getvalue()

    def _build_stream_clean_samples_key(self, session_id: str, pipeline_token: str, stream_name: StreamName) -> str:
        return f"{self._clean_root_prefix}/{session_id}/{pipeline_token}/streams/{stream_name}/samples.clean.csv.gz"

    def _build_stream_quality_key(self, session_id: str, pipeline_token: str, stream_name: StreamName) -> str:
        return f"{self._clean_root_prefix}/{session_id}/{pipeline_token}/streams/{stream_name}/quality-flags.json"

    def _build_summary_key(self, session_id: str, pipeline_token: str) -> str:
        return f"{self._clean_root_prefix}/{session_id}/{pipeline_token}/reports/preprocessing-summary.json"

    @staticmethod
    def _sanitize_token(value: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", value).strip("_")
        return sanitized or "default"

    @staticmethod
    def _duration_ms(started_at_utc: datetime, ended_at_utc: datetime) -> int:
        duration = int((ended_at_utc - started_at_utc).total_seconds() * 1000)
        return max(0, duration)

    @staticmethod
    def _format_datetime(raw_value: datetime | None) -> str:
        if raw_value is None:
            return ""
        normalized = raw_value.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_datetime(raw_value: str | None) -> datetime | None:
        if raw_value is None:
            return None

        value = raw_value.strip()
        if not value:
            return None

        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _parse_int(raw_value: str | None) -> int | None:
        if raw_value is None:
            return None

        value = raw_value.strip()
        if not value:
            return None

        try:
            if "." in value:
                return int(float(value))
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _coerce_csv_value(raw_value: str | None) -> Any:
        if raw_value is None:
            return None

        value = raw_value.strip()
        if value == "":
            return None

        lower = value.lower()
        if lower in {"true", "false"}:
            return lower == "true"

        try:
            if "." in value or lower in {"nan", "inf", "-inf"}:
                return float(value)
            return int(value)
        except ValueError:
            return value

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None

        return None

    def _extract_numeric(self, values: dict[str, Any], keys: Iterable[str]) -> float | None:
        for key in keys:
            if key not in values:
                continue
            numeric = self._as_float(values[key])
            if numeric is None or not math.isfinite(numeric):
                return None
            return numeric
        return None

    def _extract_vector_magnitude(self, values: dict[str, Any], keys: tuple[str, str, str]) -> float | None:
        extracted: list[float] = []
        for key in keys:
            numeric = self._as_float(values.get(key))
            if numeric is None or not math.isfinite(numeric):
                return None
            extracted.append(numeric)

        if len(extracted) != 3:
            return None

        return math.sqrt(sum(component * component for component in extracted))
