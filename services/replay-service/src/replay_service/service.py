from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any

from replay_service.db import Database
from replay_service.errors import ConflictError, ValidationError
from replay_service.models import (
    ReplayEvent,
    ReplayManifestResponse,
    ReplayMode,
    ReplaySample,
    ReplaySegment,
    ReplayStreamDescriptor,
    ReplayWindowRequest,
    ReplayWindowResponse,
    ReplayRunOrchestrationMode,
)
from replay_service.repository import ReplayRepository
from replay_service.storage import S3Storage

READY_INGEST_STATUSES = {"ingested", "uploaded", "validating"}


class ReplayService:
    def __init__(
        self,
        database: Database,
        storage: S3Storage,
        default_window_ms: int,
        max_window_ms: int,
        max_samples_per_stream: int,
    ) -> None:
        self._database = database
        self._storage = storage
        self._default_window_ms = default_window_ms
        self._max_window_ms = max_window_ms
        self._max_samples_per_stream = max_samples_per_stream

    def get_manifest(self, session_id: str) -> ReplayManifestResponse:
        with self._database.connection() as conn:
            repo = ReplayRepository(conn)
            session_row, segments, streams, warnings = self._load_manifest_context(repo, session_id)

        duration_ms = self._duration_ms(session_row["started_at_utc"], session_row["ended_at_utc"])
        return ReplayManifestResponse(
            session_id=session_row["session_id"],
            subject_id=session_row["subject_id"],
            ingest_status=session_row["ingest_status"],
            storage_root_prefix=session_row["storage_root_prefix"],
            started_at_utc=session_row["started_at_utc"],
            ended_at_utc=session_row["ended_at_utc"],
            timezone=session_row["timezone"],
            duration_ms=duration_ms,
            stream_count=len(streams),
            segments=segments,
            streams=streams,
            warnings=warnings,
        )

    def get_window(self, session_id: str, request: ReplayWindowRequest) -> ReplayWindowResponse:
        window_ms = request.window_ms or self._default_window_ms
        if window_ms > self._max_window_ms:
            raise ValidationError(
                code="replay_window_too_large",
                message="Requested replay window is larger than configured max window",
                details={"window_ms": window_ms, "max_window_ms": self._max_window_ms},
            )

        max_samples_per_stream = min(request.max_samples_per_stream, self._max_samples_per_stream)

        with self._database.connection() as conn:
            repo = ReplayRepository(conn)
            session_row, _, streams, warnings = self._load_manifest_context(repo, session_id)

            duration_ms = self._duration_ms(session_row["started_at_utc"], session_row["ended_at_utc"])
            from_offset_ms = request.from_offset_ms
            to_offset_ms = min(from_offset_ms + window_ms, duration_ms)
            if to_offset_ms < from_offset_ms:
                to_offset_ms = from_offset_ms

            stream_map = {stream.stream_name: stream for stream in streams}
            selected_stream_names = request.stream_names or sorted(stream_map.keys())

            unknown_stream_names = sorted(set(selected_stream_names) - set(stream_map.keys()))
            if unknown_stream_names:
                raise ValidationError(
                    code="replay_unknown_stream_name",
                    message="One or more stream_names are unknown for this session",
                    details={"unknown_stream_names": unknown_stream_names},
                )

            event_rows: list[dict[str, Any]] = []
            if request.include_events:
                window_start = session_row["started_at_utc"] + timedelta(milliseconds=from_offset_ms)
                window_end = session_row["started_at_utc"] + timedelta(milliseconds=to_offset_ms)
                event_rows = repo.list_events_between(
                    session_id=session_id,
                    started_at_utc=window_start,
                    ended_at_utc=window_end,
                )

        replay_samples: list[ReplaySample] = []
        for stream_name in selected_stream_names:
            stream = stream_map[stream_name]
            if not stream.available_for_replay:
                warnings.append(
                    f"stream {stream_name} is unavailable for replay: {stream.unavailability_reason or 'unknown reason'}"
                )
                continue

            stream_samples, truncated = self._load_stream_window_samples(
                stream=stream,
                from_offset_ms=from_offset_ms,
                to_offset_ms=to_offset_ms,
                mode=request.mode,
                speed_multiplier=request.speed_multiplier,
                max_samples=max_samples_per_stream,
            )
            replay_samples.extend(stream_samples)
            if truncated:
                warnings.append(
                    f"stream {stream_name} samples were truncated at max_samples_per_stream={max_samples_per_stream}"
                )

        replay_samples.sort(
            key=lambda sample: (
                sample.offset_ms,
                sample.stream_name,
                sample.sample_index if sample.sample_index is not None else -1,
            )
        )

        replay_events: list[ReplayEvent] = []
        if request.include_events:
            started_at_utc = session_row["started_at_utc"]
            for row in event_rows:
                event_offset_ms = max(0, self._duration_ms(started_at_utc, row["occurred_at_utc"]))
                replay_events.append(
                    ReplayEvent(
                        event_id=row["event_id"],
                        event_type=row["event_type"],
                        source=row["source"],
                        occurred_at_utc=row["occurred_at_utc"],
                        offset_ms=event_offset_ms,
                        replay_at_offset_ms=self._project_replay_offset(
                            offset_ms=event_offset_ms,
                            from_offset_ms=from_offset_ms,
                            mode=request.mode,
                            speed_multiplier=request.speed_multiplier,
                        ),
                        payload=row["payload"] or {},
                    )
                )

        next_offset_ms = to_offset_ms

        return ReplayWindowResponse(
            session_id=session_id,
            mode=request.mode,
            speed_multiplier=request.speed_multiplier,
            from_offset_ms=from_offset_ms,
            to_offset_ms=to_offset_ms,
            next_offset_ms=next_offset_ms,
            stream_names=selected_stream_names,
            sample_count=len(replay_samples),
            event_count=len(replay_events),
            samples=replay_samples,
            events=replay_events,
            warnings=warnings,
        )

    def iterate_windows(
        self,
        session_id: str,
        request: ReplayWindowRequest,
        orchestration_mode: ReplayRunOrchestrationMode,
    ) -> tuple[list[ReplayWindowResponse], int]:
        manifest = self.get_manifest(session_id)
        duration_ms = manifest.duration_ms
        current_offset_ms = request.from_offset_ms
        windows: list[ReplayWindowResponse] = []

        while current_offset_ms <= duration_ms:
            window_request = request.model_copy(update={"from_offset_ms": current_offset_ms})
            window = self.get_window(session_id=session_id, request=window_request)
            windows.append(window)

            if orchestration_mode == "single_window":
                break

            if window.next_offset_ms >= duration_ms:
                break

            if window.next_offset_ms <= current_offset_ms:
                break

            current_offset_ms = window.next_offset_ms

        return windows, duration_ms

    def _load_manifest_context(
        self,
        repo: ReplayRepository,
        session_id: str,
    ) -> tuple[dict[str, Any], list[ReplaySegment], list[ReplayStreamDescriptor], list[str]]:
        session_row = repo.get_session(session_id)
        ingest_status = session_row["ingest_status"]
        if ingest_status not in READY_INGEST_STATUSES:
            raise ConflictError(
                code="replay_session_not_ready",
                message="Session is not ready for replay",
                details={"session_id": session_id, "ingest_status": ingest_status},
            )

        segment_rows = repo.list_segments(session_id)
        stream_rows = repo.list_streams_for_manifest(session_id)

        segments = [ReplaySegment.model_validate(row) for row in segment_rows]
        streams: list[ReplayStreamDescriptor] = []
        warnings: list[str] = []

        for row in stream_rows:
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

                warnings.append(
                    f"stream {row['stream_name']} is not replayable yet ({unavailable_reason})"
                )

            streams.append(
                ReplayStreamDescriptor(
                    stream_id=row["stream_id"],
                    device_id=row["device_id"],
                    stream_name=row["stream_name"],
                    stream_kind=row["stream_kind"],
                    sample_count=row["sample_count"],
                    started_at_utc=row["started_at_utc"],
                    ended_at_utc=row["ended_at_utc"],
                    file_ref=row["file_ref"],
                    sample_object_key=row["sample_object_key"],
                    sample_content_type=row["sample_content_type"],
                    sample_upload_status=upload_status,
                    checksum_sha256=row["checksum_sha256"],
                    metadata_artifact_path=row["metadata_artifact_path"],
                    metadata_object_key=row["metadata_object_key"],
                    available_for_replay=available,
                    unavailability_reason=unavailable_reason,
                )
            )

        return session_row, segments, streams, warnings

    def _load_stream_window_samples(
        self,
        stream: ReplayStreamDescriptor,
        from_offset_ms: int,
        to_offset_ms: int,
        mode: ReplayMode,
        speed_multiplier: float,
        max_samples: int,
    ) -> tuple[list[ReplaySample], bool]:
        if not stream.sample_object_key:
            raise ValidationError(
                code="replay_missing_object_key",
                message="Stream has no sample object key",
                details={"stream_name": stream.stream_name},
            )

        text_payload = self._storage.read_text(stream.sample_object_key)
        reader = csv.DictReader(StringIO(text_payload))
        if not reader.fieldnames:
            return [], False

        if "offset_ms" not in reader.fieldnames:
            raise ValidationError(
                code="replay_missing_offset_ms",
                message="Replay sample file has no offset_ms column",
                details={"stream_name": stream.stream_name, "object_key": stream.sample_object_key},
            )

        output: list[ReplaySample] = []
        truncated = False
        for row in reader:
            offset_ms = self._parse_int(row.get("offset_ms"))
            if offset_ms is None:
                continue
            if offset_ms < from_offset_ms:
                continue
            if offset_ms > to_offset_ms:
                break

            sample_index = self._parse_int(row.get("sample_index"))
            timestamp_utc = self._parse_datetime(row.get("timestamp_utc"))

            values: dict[str, Any] = {}
            for key, value in row.items():
                if key in {"sample_index", "offset_ms", "timestamp_utc", "source_timestamp", "ingested_at_utc"}:
                    continue
                values[key] = self._coerce_csv_value(value)

            output.append(
                ReplaySample(
                    stream_name=stream.stream_name,
                    stream_id=stream.stream_id,
                    device_id=stream.device_id,
                    sample_index=sample_index,
                    offset_ms=offset_ms,
                    timestamp_utc=timestamp_utc,
                    replay_at_offset_ms=self._project_replay_offset(
                        offset_ms=offset_ms,
                        from_offset_ms=from_offset_ms,
                        mode=mode,
                        speed_multiplier=speed_multiplier,
                    ),
                    values=values,
                )
            )

            if len(output) >= max_samples:
                truncated = True
                break

        return output, truncated

    @staticmethod
    def _duration_ms(started_at_utc: datetime, ended_at_utc: datetime) -> int:
        duration = int((ended_at_utc - started_at_utc).total_seconds() * 1000)
        return max(0, duration)

    @staticmethod
    def _project_replay_offset(
        offset_ms: int,
        from_offset_ms: int,
        mode: ReplayMode,
        speed_multiplier: float,
    ) -> int:
        if mode == "realtime":
            return offset_ms

        delta = max(0, offset_ms - from_offset_ms)
        accelerated_delta = int(delta / speed_multiplier)
        return from_offset_ms + accelerated_delta

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
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
