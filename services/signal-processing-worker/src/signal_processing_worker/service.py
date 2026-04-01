from __future__ import annotations

import csv
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from io import StringIO
from statistics import median, pstdev
from typing import Any, Iterable, Literal

from signal_processing_worker.db import Database
from signal_processing_worker.errors import ConflictError, ValidationError
from signal_processing_worker.models import (
    CleanSample,
    FeatureWindow,
    OffsetInterval,
    PreprocessingRunResult,
    ProcessedStream,
    QualityCheck,
    QualityStatus,
    RawSample,
    RawStreamDescriptor,
    StreamFeatureSummary,
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
    "polar_hr": {
        "hr_bpm": (25.0, 240.0),
        "contact": (0.0, 1.0),
        "contact_supported": (0.0, 1.0),
    },
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

DEFAULT_WINDOW_CONFIG_MS: dict[StreamName, tuple[int, int]] = {
    "polar_ecg": (5000, 2500),
    "polar_rr": (30000, 10000),
    "polar_hr": (15000, 5000),
    "polar_acc": (5000, 2500),
    "watch_heart_rate": (30000, 10000),
    "watch_accelerometer": (5000, 2500),
    "watch_gyroscope": (5000, 2500),
    "watch_activity_context": (60000, 15000),
    "watch_hrv": (120000, 30000),
}

FEATURE_FAMILY_SELECTORS: dict[str, tuple[str, ...]] = {
    "polar_cardio_core": (
        "hr_bpm__mean",
        "hr_bpm__std",
        "rr_like__mean_rr",
        "rr_like__median_rr",
        "rr_like__sdnn",
        "rr_like__rmssd",
        "rr_like__mean_hr",
        "rr_like__nn50",
        "rr_like__pnn50",
        "ecg_sample_count",
        "ecg_coverage_ratio",
        "ecg_peak_success_ratio",
        "ecg_noise_ratio",
    ),
    "polar_cardio_extended": (
        "rr_like__*",
        "ecg_*",
    ),
    "watch_motion_core": (
        "motion_artifact_ratio",
        "acc_mag__*",
        "gyro_mag__*",
        "acc_x_g__*",
        "acc_y_g__*",
        "acc_z_g__*",
        "activity_label__mode",
        "confidence__mean",
    ),
}

QUALITY_GATE_POLICY_VERSION = "p2-offline-v1"


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
                features_key = self._build_stream_features_key(session_id, pipeline_token, descriptor.stream_name)

                clean_csv = self._render_clean_samples_csv(processed_stream)
                feature_csv = self._render_feature_windows_csv(processed_stream)
                self._storage.write_clean_text(
                    object_key=clean_key,
                    text=clean_csv,
                    content_type="text/csv",
                    gzip_compress=True,
                )
                self._storage.write_clean_text(
                    object_key=features_key,
                    text=feature_csv,
                    content_type="text/csv",
                    gzip_compress=True,
                )
                self._storage.write_clean_json(
                    object_key=quality_key,
                    payload=processed_stream.quality.model_dump(mode="json"),
                )

                processed_stream.clean_samples_object_key = clean_key
                processed_stream.quality_report_object_key = quality_key
                processed_stream.features_object_key = features_key

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
        feature_windows, feature_summary, gate_metrics = self._extract_stream_features(
            stream_name=descriptor.stream_name,
            clean_samples=clean_samples,
        )
        if gate_metrics["dropped_windows"] > 0:
            quality_warnings.append(
                f"quality_gate dropped {gate_metrics['dropped_windows']} feature windows ({QUALITY_GATE_POLICY_VERSION})"
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
            rr_quality_gate_status=gate_metrics["rr_quality_gate_status"],
            ecg_quality_gate_status=gate_metrics["ecg_quality_gate_status"],
            quality_gate_policy=QUALITY_GATE_POLICY_VERSION,
            quality_gate_marked_window_count=gate_metrics["marked_windows"],
            quality_gate_dropped_window_count=gate_metrics["dropped_windows"],
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
            feature_windows=feature_windows,
            feature_summary=feature_summary,
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
                        "rr_quality_gate_status": stream.quality.rr_quality_gate_status,
                        "ecg_quality_gate_status": stream.quality.ecg_quality_gate_status,
                        "quality_gate_marked_window_count": stream.quality.quality_gate_marked_window_count,
                        "quality_gate_dropped_window_count": stream.quality.quality_gate_dropped_window_count,
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

    def _extract_stream_features(
        self,
        stream_name: StreamName,
        clean_samples: list[CleanSample],
    ) -> tuple[list[FeatureWindow], StreamFeatureSummary, dict[str, Any]]:
        window_size_ms, step_size_ms = DEFAULT_WINDOW_CONFIG_MS.get(stream_name, (15000, 5000))

        if not clean_samples:
            return (
                [],
                StreamFeatureSummary(
                    window_size_ms=window_size_ms,
                    step_size_ms=step_size_ms,
                    window_count=0,
                    covered_duration_ms=0,
                    feature_names=[],
                    feature_family_selectors=self._feature_family_selectors_for_summary(),
                    feature_family_tags=[],
                    quality_gate_policy=QUALITY_GATE_POLICY_VERSION,
                    quality_gate_kept_windows=0,
                    quality_gate_marked_windows=0,
                    quality_gate_dropped_windows=0,
                    warnings=["no clean samples available for feature extraction"],
                ),
                {
                    "marked_windows": 0,
                    "dropped_windows": 0,
                    "rr_quality_gate_status": "pass",
                    "ecg_quality_gate_status": "pass",
                },
            )

        sorted_samples = sorted(clean_samples, key=lambda sample: sample.aligned_offset_ms)
        stream_start = sorted_samples[0].aligned_offset_ms
        stream_end = sorted_samples[-1].aligned_offset_ms
        covered_duration_ms = max(0, stream_end - stream_start)

        window_start = stream_start
        right_cursor = 0
        left_cursor = 0
        windows: list[FeatureWindow] = []
        all_feature_names: set[str] = set()
        all_family_tags: set[str] = set()
        marked_windows = 0
        dropped_windows = 0
        rr_quality_statuses: list[QualityStatus] = []
        ecg_quality_statuses: list[QualityStatus] = []

        while window_start <= stream_end:
            window_end = window_start + window_size_ms

            while left_cursor < len(sorted_samples) and sorted_samples[left_cursor].aligned_offset_ms < window_start:
                left_cursor += 1
            if right_cursor < left_cursor:
                right_cursor = left_cursor
            while right_cursor < len(sorted_samples) and sorted_samples[right_cursor].aligned_offset_ms < window_end:
                right_cursor += 1

            window_samples = sorted_samples[left_cursor:right_cursor]
            if window_samples:
                feature_values = self._compute_window_features(stream_name=stream_name, samples=window_samples)
                family_tags = self._resolve_feature_family_tags(feature_values.keys())
                quality_gate_status, quality_gate_action, quality_gate_flags = self._evaluate_window_quality_gate(
                    stream_name=stream_name,
                    window_size_ms=window_size_ms,
                    feature_values=feature_values,
                )
                if any(flag.startswith("rr_") for flag in quality_gate_flags):
                    rr_quality_statuses.append(quality_gate_status)
                if any(flag.startswith("ecg_") for flag in quality_gate_flags):
                    ecg_quality_statuses.append(quality_gate_status)

                if quality_gate_action == "drop":
                    dropped_windows += 1
                else:
                    all_feature_names.update(feature_values.keys())
                    all_family_tags.update(family_tags)
                    if quality_gate_action == "mark":
                        marked_windows += 1
                    windows.append(
                        FeatureWindow(
                            window_index=len(windows),
                            started_offset_ms=window_start,
                            ended_offset_ms=window_end,
                            sample_count=len(window_samples),
                            feature_family_tags=family_tags,
                            quality_gate_status=quality_gate_status,
                            quality_gate_action=quality_gate_action,
                            quality_gate_flags=quality_gate_flags,
                            values=feature_values,
                        )
                    )

            window_start += step_size_ms

        warnings: list[str] = []
        if dropped_windows > 0:
            warnings.append(f"quality_gate dropped {dropped_windows} windows")

        return (
            windows,
            StreamFeatureSummary(
                window_size_ms=window_size_ms,
                step_size_ms=step_size_ms,
                window_count=len(windows),
                covered_duration_ms=covered_duration_ms,
                feature_names=sorted(all_feature_names),
                feature_family_selectors=self._feature_family_selectors_for_summary(),
                feature_family_tags=sorted(all_family_tags),
                quality_gate_policy=QUALITY_GATE_POLICY_VERSION,
                quality_gate_kept_windows=len(windows) - marked_windows,
                quality_gate_marked_windows=marked_windows,
                quality_gate_dropped_windows=dropped_windows,
                warnings=warnings,
            ),
            {
                "marked_windows": marked_windows,
                "dropped_windows": dropped_windows,
                "rr_quality_gate_status": self._merge_quality_status(rr_quality_statuses),
                "ecg_quality_gate_status": self._merge_quality_status(ecg_quality_statuses),
            },
        )

    def _compute_window_features(self, stream_name: StreamName, samples: list[CleanSample]) -> dict[str, Any]:
        features: dict[str, Any] = {}
        features["sample_count"] = len(samples)
        features["window_duration_ms"] = max(
            0,
            samples[-1].aligned_offset_ms - samples[0].aligned_offset_ms,
        )
        flagged = sum(1 for sample in samples if "motion_artifact" in sample.quality_flags)
        features["motion_artifact_ratio"] = round(flagged / len(samples), 6) if samples else 0.0

        numeric_by_key: dict[str, list[float]] = {}
        non_numeric_by_key: dict[str, list[str]] = {}

        for sample in samples:
            for key, value in sample.values.items():
                numeric = self._as_float(value)
                if numeric is not None and math.isfinite(numeric):
                    numeric_by_key.setdefault(key, []).append(numeric)
                    continue
                if value is None:
                    continue
                non_numeric_by_key.setdefault(key, []).append(str(value))

        for key, values in numeric_by_key.items():
            if not values:
                continue
            features[f"{key}__mean"] = round(sum(values) / len(values), 6)
            features[f"{key}__std"] = round(pstdev(values), 6) if len(values) >= 2 else 0.0
            features[f"{key}__min"] = min(values)
            features[f"{key}__max"] = max(values)
            features[f"{key}__last"] = values[-1]

        if stream_name in {"polar_acc", "watch_accelerometer"}:
            axis = ("acc_x_mg", "acc_y_mg", "acc_z_mg") if stream_name == "polar_acc" else ("acc_x_g", "acc_y_g", "acc_z_g")
            self._add_vector_magnitude_features(features, samples, axis, prefix="acc_mag")
        elif stream_name == "watch_gyroscope":
            axis = ("gyro_x_rad_s", "gyro_y_rad_s", "gyro_z_rad_s")
            self._add_vector_magnitude_features(features, samples, axis, prefix="gyro_mag")

        rr_like = numeric_by_key.get("rr_ms") or numeric_by_key.get("hrv_ms")
        if rr_like and len(rr_like) >= 2:
            self._add_rr_like_features(features=features, rr_values=rr_like, samples=samples)

        if stream_name == "polar_ecg":
            ecg_values = numeric_by_key.get("voltage_uv")
            if ecg_values:
                self._add_ecg_quality_features(features=features, ecg_values=ecg_values, samples=samples)

        if stream_name == "polar_acc":
            self._add_polar_acc_features(features=features, samples=samples)

        for key, values in non_numeric_by_key.items():
            if not values:
                continue
            mode = Counter(values).most_common(1)[0][0]
            features[f"{key}__mode"] = mode

        return features

    def _evaluate_window_quality_gate(
        self,
        stream_name: StreamName,
        window_size_ms: int,
        feature_values: dict[str, Any],
    ) -> tuple[QualityStatus, Literal["keep", "mark", "drop"], list[str]]:
        flags: list[str] = []
        action: Literal["keep", "mark", "drop"] = "keep"

        rr_valid_count = self._as_float(feature_values.get("rr_like__valid_count"))
        rr_outlier_ratio = self._as_float(feature_values.get("rr_like__outlier_ratio"))
        rr_window_duration = self._as_float(feature_values.get("rr_like__window_duration_ms"))
        if rr_valid_count is not None:
            if rr_valid_count < 2:
                flags.append("rr_low_valid_count")
                action = "drop"
            elif rr_valid_count < 4 and action != "drop":
                flags.append("rr_low_valid_count_soft")
                action = "mark"
        if rr_outlier_ratio is not None:
            if rr_outlier_ratio >= 0.35:
                flags.append("rr_high_outlier_ratio")
                action = "drop"
            elif rr_outlier_ratio >= 0.2 and action != "drop":
                flags.append("rr_elevated_outlier_ratio")
                action = "mark"
        if rr_window_duration is not None and action != "drop":
            min_rr_duration = max(5000.0, float(window_size_ms) * 0.4)
            if rr_window_duration < min_rr_duration:
                flags.append("rr_short_window_duration")
                action = "mark"

        ecg_coverage = self._as_float(feature_values.get("ecg_coverage_ratio"))
        ecg_noise = self._as_float(feature_values.get("ecg_noise_ratio"))
        ecg_peak_success = self._as_float(feature_values.get("ecg_peak_success_ratio"))
        if ecg_coverage is not None:
            if ecg_coverage < 0.6:
                flags.append("ecg_low_coverage")
                action = "drop"
            elif ecg_coverage < 0.8 and action != "drop":
                flags.append("ecg_reduced_coverage")
                action = "mark"
        if ecg_noise is not None:
            if ecg_noise > 0.45:
                flags.append("ecg_high_noise")
                action = "drop"
            elif ecg_noise > 0.25 and action != "drop":
                flags.append("ecg_elevated_noise")
                action = "mark"
        if ecg_peak_success is not None and ecg_peak_success < 0.01 and action != "drop":
            flags.append("ecg_low_peak_success_ratio")
            action = "mark"

        if stream_name.startswith("watch_") and "motion_artifact_ratio" in feature_values:
            motion_ratio = self._as_float(feature_values.get("motion_artifact_ratio")) or 0.0
            if motion_ratio > 0.6 and action != "drop":
                flags.append("watch_motion_high_artifact_ratio")
                action = "mark"

        if action == "drop":
            return "fail", action, flags
        if action == "mark":
            return "warning", action, flags
        return "pass", action, flags

    def _resolve_feature_family_tags(self, feature_keys: Iterable[str]) -> list[str]:
        tags: list[str] = []
        keys = list(feature_keys)
        for family, selectors in FEATURE_FAMILY_SELECTORS.items():
            for selector in selectors:
                if any(self._feature_key_matches_selector(key, selector) for key in keys):
                    tags.append(family)
                    break
        return sorted(tags)

    @staticmethod
    def _feature_key_matches_selector(feature_key: str, selector: str) -> bool:
        if selector.endswith("*"):
            return feature_key.startswith(selector[:-1])
        return feature_key == selector

    @staticmethod
    def _feature_family_selectors_for_summary() -> dict[str, list[str]]:
        return {family: list(selectors) for family, selectors in FEATURE_FAMILY_SELECTORS.items()}

    @staticmethod
    def _merge_quality_status(statuses: list[QualityStatus]) -> QualityStatus:
        if not statuses:
            return "pass"
        if any(status == "fail" for status in statuses):
            return "fail"
        if any(status == "warning" for status in statuses):
            return "warning"
        return "pass"

    def _add_rr_like_features(self, features: dict[str, Any], rr_values: list[float], samples: list[CleanSample]) -> None:
        if len(rr_values) < 2:
            return

        rr_diffs = [rr_values[index] - rr_values[index - 1] for index in range(1, len(rr_values))]
        abs_diffs = [abs(delta) for delta in rr_diffs]
        mean_sq = sum(delta * delta for delta in rr_diffs) / len(rr_diffs)
        rmssd = math.sqrt(mean_sq)
        sdnn = pstdev(rr_values) if len(rr_values) >= 2 else 0.0
        sdsd = pstdev(rr_diffs) if len(rr_diffs) >= 2 else 0.0
        mean_rr = sum(rr_values) / len(rr_values)
        median_rr = median(rr_values)
        mean_abs_diff = sum(abs_diffs) / len(abs_diffs) if abs_diffs else 0.0
        median_abs_diff = median(abs_diffs) if abs_diffs else 0.0
        rr_sorted = sorted(rr_values)
        rr_iqr = self._percentile(rr_sorted, 75.0) - self._percentile(rr_sorted, 25.0)
        mad_rr = median([abs(item - median_rr) for item in rr_values])
        rr_p10 = self._percentile(rr_sorted, 10.0)
        rr_p90 = self._percentile(rr_sorted, 90.0)
        nn20 = sum(1 for delta in abs_diffs if delta > 20.0)
        nn50 = sum(1 for delta in abs_diffs if delta > 50.0)
        pnn20 = (nn20 / len(abs_diffs)) * 100.0 if abs_diffs else 0.0
        pnn50 = (nn50 / len(abs_diffs)) * 100.0 if abs_diffs else 0.0
        cvnn = (sdnn / mean_rr) * 100.0 if mean_rr > 0 else 0.0
        cvsd = (rmssd / mean_rr) * 100.0 if mean_rr > 0 else 0.0
        hr_values = [60000.0 / item for item in rr_values if item > 0]
        hr_min = min(hr_values) if hr_values else 0.0
        hr_max = max(hr_values) if hr_values else 0.0
        hr_range = hr_max - hr_min if hr_values else 0.0
        mean_hr = (sum(hr_values) / len(hr_values)) if hr_values else 0.0

        # Poincare plot descriptors, robust on short RR windows.
        var_rr = self._variance(rr_values)
        var_diff = self._variance(rr_diffs)
        sd1 = math.sqrt(max(0.0, 0.5 * var_diff))
        sd2_sq = max(0.0, (2.0 * var_rr) - (0.5 * var_diff))
        sd2 = math.sqrt(sd2_sq)
        sd1_sd2_ratio = (sd1 / sd2) if sd2 > 0 else 0.0

        rr_hist_entropy = self._shannon_entropy(rr_values)
        rr_triangular_index = self._rr_triangular_index(rr_values)
        sample_entropy = self._sample_entropy(rr_values, m=2, r_scale=0.2)
        vlf_power, lf_power, hf_power = self._rr_band_powers(rr_values)
        lf_hf_ratio = (lf_power / hf_power) if hf_power > 0 else 0.0
        lf_nu = (lf_power / (lf_power + hf_power)) * 100.0 if (lf_power + hf_power) > 0 else 0.0
        hf_nu = (hf_power / (lf_power + hf_power)) * 100.0 if (lf_power + hf_power) > 0 else 0.0

        window_duration_ms = max(0, samples[-1].aligned_offset_ms - samples[0].aligned_offset_ms) if samples else 0

        features["rr_like__valid_count"] = len(rr_values)
        features["rr_like__window_duration_ms"] = window_duration_ms
        features["rr_like__mean_rr"] = round(mean_rr, 6)
        features["rr_like__median_rr"] = round(median_rr, 6)
        features["rr_like__min_rr"] = round(min(rr_values), 6)
        features["rr_like__max_rr"] = round(max(rr_values), 6)
        features["rr_like__rr_p10"] = round(rr_p10, 6)
        features["rr_like__rr_p90"] = round(rr_p90, 6)
        features["rr_like__sdnn"] = round(sdnn, 6)
        features["rr_like__rmssd"] = round(rmssd, 6)
        features["rr_like__sdsd"] = round(sdsd, 6)
        features["rr_like__mean_abs_diff"] = round(mean_abs_diff, 6)
        features["rr_like__median_abs_diff"] = round(median_abs_diff, 6)
        features["rr_like__nn20"] = nn20
        features["rr_like__pnn20"] = round(pnn20, 6)
        features["rr_like__nn50"] = nn50
        features["rr_like__pnn50"] = round(pnn50, 6)
        features["rr_like__cvnn"] = round(cvnn, 6)
        features["rr_like__cvsd"] = round(cvsd, 6)
        features["rr_like__rr_range"] = round(max(rr_values) - min(rr_values), 6)
        features["rr_like__rr_iqr"] = round(rr_iqr, 6)
        features["rr_like__mad_rr"] = round(mad_rr, 6)
        features["rr_like__mean_hr"] = round(mean_hr, 6)
        features["rr_like__hr_min"] = round(hr_min, 6)
        features["rr_like__hr_max"] = round(hr_max, 6)
        features["rr_like__hr_range"] = round(hr_range, 6)
        features["rr_like__sd1"] = round(sd1, 6)
        features["rr_like__sd2"] = round(sd2, 6)
        features["rr_like__sd1_sd2_ratio"] = round(sd1_sd2_ratio, 6)
        features["rr_like__triangular_index"] = round(rr_triangular_index, 6)
        features["rr_like__shannon_entropy"] = round(rr_hist_entropy, 6)
        features["rr_like__sample_entropy_m2_r02"] = round(sample_entropy, 6)
        features["rr_like__vlf_power"] = round(vlf_power, 6)
        features["rr_like__lf_power"] = round(lf_power, 6)
        features["rr_like__hf_power"] = round(hf_power, 6)
        features["rr_like__lf_hf_ratio"] = round(lf_hf_ratio, 6)
        features["rr_like__lf_nu"] = round(lf_nu, 6)
        features["rr_like__hf_nu"] = round(hf_nu, 6)
        features["rr_like__outlier_ratio"] = round(
            (sum(1 for delta in abs_diffs if delta > 200.0) / len(abs_diffs)) if abs_diffs else 0.0,
            6,
        )

    def _add_ecg_quality_features(self, features: dict[str, Any], ecg_values: list[float], samples: list[CleanSample]) -> None:
        if not ecg_values:
            return

        sample_count = len(ecg_values)
        window_duration_ms = max(0, samples[-1].aligned_offset_ms - samples[0].aligned_offset_ms) if samples else 0
        expected_samples = max(1, int(window_duration_ms / DEFAULT_INTERVAL_MS["polar_ecg"]) + 1)
        coverage_ratio = min(1.0, sample_count / expected_samples)

        mean_voltage = sum(ecg_values) / sample_count
        std_voltage = pstdev(ecg_values) if sample_count >= 2 else 0.0
        baseline_wander_score = abs(mean_voltage) / (std_voltage + 1e-6)

        noise_threshold = max(1000.0, (std_voltage * 3.0))
        noisy_transitions = 0
        for previous, current in zip(ecg_values, ecg_values[1:]):
            if abs(current - previous) > noise_threshold:
                noisy_transitions += 1
        noise_ratio = (noisy_transitions / max(1, sample_count - 1)) if sample_count >= 2 else 0.0

        peak_count = self._count_local_peaks(ecg_values, min_height=mean_voltage + std_voltage)
        peak_success_ratio = peak_count / sample_count if sample_count > 0 else 0.0

        features["ecg_sample_count"] = sample_count
        features["ecg_coverage_ratio"] = round(coverage_ratio, 6)
        features["ecg_peak_count"] = peak_count
        features["ecg_peak_success_ratio"] = round(peak_success_ratio, 6)
        features["ecg_noise_ratio"] = round(noise_ratio, 6)
        features["ecg_baseline_wander_score"] = round(baseline_wander_score, 6)

    def _add_polar_acc_features(self, features: dict[str, Any], samples: list[CleanSample]) -> None:
        magnitudes: list[float] = []
        offsets: list[int] = []
        for sample in samples:
            magnitude = self._extract_vector_magnitude(sample.values, ("acc_x_mg", "acc_y_mg", "acc_z_mg"))
            if magnitude is None or not math.isfinite(magnitude):
                continue
            magnitudes.append(magnitude)
            offsets.append(sample.aligned_offset_ms)

        if len(magnitudes) < 2:
            return

        energy = sum(value * value for value in magnitudes) / len(magnitudes)
        stationary_ratio = sum(1 for value in magnitudes if value < 1100.0) / len(magnitudes)
        burst_count = sum(1 for value in magnitudes if value > 2500.0)

        jerk_values: list[float] = []
        for index in range(1, len(magnitudes)):
            delta_time_s = max(0.001, (offsets[index] - offsets[index - 1]) / 1000.0)
            jerk_values.append(abs(magnitudes[index] - magnitudes[index - 1]) / delta_time_s)

        jerk_mean = sum(jerk_values) / len(jerk_values) if jerk_values else 0.0
        jerk_std = pstdev(jerk_values) if len(jerk_values) >= 2 else 0.0

        features["polar_acc__energy"] = round(energy, 6)
        features["polar_acc__jerk_mean"] = round(jerk_mean, 6)
        features["polar_acc__jerk_std"] = round(jerk_std, 6)
        features["polar_acc__stationary_ratio"] = round(stationary_ratio, 6)
        features["polar_acc__motion_burst_count"] = burst_count

    def _add_vector_magnitude_features(
        self,
        output: dict[str, Any],
        samples: list[CleanSample],
        axis: tuple[str, str, str],
        prefix: str,
    ) -> None:
        magnitudes: list[float] = []
        for sample in samples:
            magnitude = self._extract_vector_magnitude(sample.values, axis)
            if magnitude is None or not math.isfinite(magnitude):
                continue
            magnitudes.append(magnitude)

        if not magnitudes:
            return

        output[f"{prefix}__mean"] = round(sum(magnitudes) / len(magnitudes), 6)
        output[f"{prefix}__std"] = round(pstdev(magnitudes), 6) if len(magnitudes) >= 2 else 0.0
        output[f"{prefix}__max"] = max(magnitudes)
        output[f"{prefix}__last"] = magnitudes[-1]

    def _render_feature_windows_csv(self, processed_stream: ProcessedStream) -> str:
        windows = processed_stream.feature_windows
        value_keys: set[str] = set()
        for window in windows:
            value_keys.update(window.values.keys())

        fieldnames = [
            "window_index",
            "started_offset_ms",
            "ended_offset_ms",
            "sample_count",
            "feature_family_tags",
            "quality_gate_status",
            "quality_gate_action",
            "quality_gate_flags",
            *sorted(value_keys),
        ]

        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()

        for window in windows:
            row: dict[str, Any] = {
                "window_index": window.window_index,
                "started_offset_ms": window.started_offset_ms,
                "ended_offset_ms": window.ended_offset_ms,
                "sample_count": window.sample_count,
                "feature_family_tags": "|".join(window.feature_family_tags),
                "quality_gate_status": window.quality_gate_status,
                "quality_gate_action": window.quality_gate_action,
                "quality_gate_flags": "|".join(window.quality_gate_flags),
            }
            for key in value_keys:
                row[key] = window.values.get(key)
            writer.writerow(row)

        return buffer.getvalue()

    def _build_stream_clean_samples_key(self, session_id: str, pipeline_token: str, stream_name: StreamName) -> str:
        return f"{self._clean_root_prefix}/{session_id}/{pipeline_token}/streams/{stream_name}/samples.clean.csv.gz"

    def _build_stream_quality_key(self, session_id: str, pipeline_token: str, stream_name: StreamName) -> str:
        return f"{self._clean_root_prefix}/{session_id}/{pipeline_token}/streams/{stream_name}/quality-flags.json"

    def _build_stream_features_key(self, session_id: str, pipeline_token: str, stream_name: StreamName) -> str:
        return f"{self._clean_root_prefix}/{session_id}/{pipeline_token}/features/{stream_name}/windows.features.csv.gz"

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

    def _shannon_entropy(self, values: list[float], bins: int = 10) -> float:
        if len(values) < 2:
            return 0.0

        low = min(values)
        high = max(values)
        if high <= low:
            return 0.0

        step = (high - low) / bins
        if step <= 0:
            return 0.0

        counts = [0] * bins
        for value in values:
            idx = int((value - low) / step)
            if idx >= bins:
                idx = bins - 1
            if idx < 0:
                idx = 0
            counts[idx] += 1

        total = len(values)
        entropy = 0.0
        for count in counts:
            if count <= 0:
                continue
            probability = count / total
            entropy -= probability * math.log(probability)
        return entropy

    def _rr_triangular_index(self, rr_values: list[float], bin_width_ms: float = 7.8125) -> float:
        if len(rr_values) < 2 or bin_width_ms <= 0:
            return 0.0

        low = min(rr_values)
        high = max(rr_values)
        if high <= low:
            return 0.0

        bins = max(1, int(math.ceil((high - low) / bin_width_ms)))
        counts = [0] * bins
        for value in rr_values:
            idx = int((value - low) / bin_width_ms)
            if idx >= bins:
                idx = bins - 1
            if idx < 0:
                idx = 0
            counts[idx] += 1

        peak = max(counts) if counts else 0
        if peak <= 0:
            return 0.0
        return len(rr_values) / peak

    def _sample_entropy(self, values: list[float], m: int, r_scale: float) -> float:
        if len(values) < m + 2:
            return 0.0
        sigma = pstdev(values) if len(values) >= 2 else 0.0
        if sigma <= 0:
            return 0.0
        r = r_scale * sigma
        if r <= 0:
            return 0.0

        def _count_matches(length: int) -> int:
            count = 0
            limit = len(values) - length + 1
            for i in range(limit):
                for j in range(i + 1, limit):
                    distance = 0.0
                    for k in range(length):
                        distance = max(distance, abs(values[i + k] - values[j + k]))
                    if distance <= r:
                        count += 1
            return count

        b = _count_matches(m)
        a = _count_matches(m + 1)
        if b <= 0 or a <= 0:
            return 0.0
        return -math.log(a / b)

    def _rr_band_powers(self, rr_values: list[float]) -> tuple[float, float, float]:
        if len(rr_values) < 4:
            return 0.0, 0.0, 0.0

        sample_rate_hz = 4.0
        step_s = 1.0 / sample_rate_hz

        times_s: list[float] = [0.0]
        for value in rr_values[:-1]:
            times_s.append(times_s[-1] + max(0.001, value / 1000.0))

        duration_s = times_s[-1]
        if duration_s <= step_s:
            return 0.0, 0.0, 0.0

        resampled: list[float] = []
        target_t = 0.0
        cursor = 0
        while target_t <= duration_s:
            while cursor + 1 < len(times_s) and times_s[cursor + 1] < target_t:
                cursor += 1

            if cursor + 1 < len(times_s):
                left_t = times_s[cursor]
                right_t = times_s[cursor + 1]
                left_v = rr_values[cursor]
                right_v = rr_values[cursor + 1]
                span = max(1e-6, right_t - left_t)
                alpha = (target_t - left_t) / span
                value = left_v + alpha * (right_v - left_v)
            else:
                value = rr_values[-1]

            resampled.append(value)
            target_t += step_s

        if len(resampled) < 8:
            return 0.0, 0.0, 0.0

        mean_value = sum(resampled) / len(resampled)
        detrended = [value - mean_value for value in resampled]
        freq_resolution = sample_rate_hz / len(detrended)

        vlf_power = 0.0
        lf_power = 0.0
        hf_power = 0.0
        max_k = len(detrended) // 2

        for k in range(1, max_k + 1):
            frequency = k * freq_resolution
            real = 0.0
            imag = 0.0
            for n, value in enumerate(detrended):
                angle = 2.0 * math.pi * k * n / len(detrended)
                real += value * math.cos(angle)
                imag -= value * math.sin(angle)
            power = (real * real + imag * imag) / len(detrended)

            if 0.0033 <= frequency < 0.04:
                vlf_power += power
            elif 0.04 <= frequency < 0.15:
                lf_power += power
            elif 0.15 <= frequency <= 0.40:
                hf_power += power

        return vlf_power, lf_power, hf_power

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

    @staticmethod
    def _variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean_value = sum(values) / len(values)
        return sum((item - mean_value) * (item - mean_value) for item in values) / len(values)

    @staticmethod
    def _percentile(sorted_values: list[float], q: float) -> float:
        if not sorted_values:
            return 0.0
        if len(sorted_values) == 1:
            return sorted_values[0]

        position = (len(sorted_values) - 1) * (q / 100.0)
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            return sorted_values[lower]
        weight = position - lower
        return (sorted_values[lower] * (1.0 - weight)) + (sorted_values[upper] * weight)

    @staticmethod
    def _count_local_peaks(values: list[float], min_height: float) -> int:
        if len(values) < 3:
            return 0
        count = 0
        for index in range(1, len(values) - 1):
            current = values[index]
            if current >= min_height and current > values[index - 1] and current > values[index + 1]:
                count += 1
        return count
