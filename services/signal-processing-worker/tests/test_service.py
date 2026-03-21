from __future__ import annotations

from datetime import datetime, timezone

from signal_processing_worker.models import RawSample, RawStreamDescriptor
from signal_processing_worker.service import SignalProcessingService


def _service() -> SignalProcessingService:
    return SignalProcessingService(
        database=None,  # type: ignore[arg-type]
        storage=None,  # type: ignore[arg-type]
        clean_root_prefix="clean-sessions",
        preprocessing_version="e1-v1",
        gap_factor=1.8,
        max_samples_per_stream=10000,
        persist_outputs=False,
    )


def test_alignment_delta_estimation_is_applied_to_clean_samples() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-watch-hr",
        device_id="watch-1",
        stream_name="watch_heart_rate",
        stream_kind="timeseries",
        sample_count=3,
        file_ref="streams/watch_heart_rate/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=200, timestamp_utc="2026-03-21T10:00:00Z", values={"hr_bpm": 80}),
        RawSample(sample_index=1, offset_ms=1200, timestamp_utc="2026-03-21T10:00:01Z", values={"hr_bpm": 82}),
        RawSample(sample_index=2, offset_ms=2200, timestamp_utc="2026-03-21T10:00:02Z", values={"hr_bpm": 83}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    assert processed.alignment_delta_ms == 200
    assert [sample.aligned_offset_ms for sample in processed.clean_samples] == [0, 1000, 2000]


def test_gap_and_packet_loss_are_detected_for_regular_streams() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-hr",
        device_id="polar-1",
        stream_name="polar_hr",
        stream_kind="timeseries",
        sample_count=3,
        file_ref="streams/polar_hr/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"hr_bpm": 80}),
        RawSample(sample_index=1, offset_ms=1000, values={"hr_bpm": 81}),
        RawSample(sample_index=2, offset_ms=4000, values={"hr_bpm": 82}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    assert processed.quality.gap_count == 1
    assert processed.quality.packet_loss_estimated_samples == 2
    assert processed.quality.gap_intervals[0].started_offset_ms == 1000
    assert processed.quality.gap_intervals[0].ended_offset_ms == 4000


def test_noisy_samples_are_dropped_and_motion_artifact_is_marked() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-watch-hr",
        device_id="watch-1",
        stream_name="watch_heart_rate",
        stream_kind="timeseries",
        sample_count=3,
        file_ref="streams/watch_heart_rate/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"hr_bpm": 80}),
        RawSample(sample_index=1, offset_ms=1000, values={"hr_bpm": 120}),
        RawSample(sample_index=2, offset_ms=2000, values={"hr_bpm": 300}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    assert processed.clean_sample_count == 2
    assert processed.quality.noisy_sample_count == 1
    assert processed.quality.motion_artifact_count == 1
    assert processed.clean_samples[1].quality_flags == ["motion_artifact"]
