from __future__ import annotations

from datetime import datetime, timezone

from signal_processing_worker.models import CleanSample, OffsetInterval, ProcessedStream, StreamQualitySummary


def test_offset_interval_requires_order() -> None:
    try:
        OffsetInterval.model_validate(
            {
                "started_offset_ms": 100,
                "ended_offset_ms": 90,
                "reason": "gap_detected",
            }
        )
    except Exception as exc:
        assert "ended_offset_ms must be >= started_offset_ms" in str(exc)
        return

    raise AssertionError("Validation should fail when ended_offset_ms < started_offset_ms")


def test_processed_stream_excludes_runtime_clean_samples_from_dump() -> None:
    stream = ProcessedStream(
        stream_name="polar_hr",
        stream_id="stream-1",
        device_id="polar-1",
        raw_sample_count=1,
        clean_sample_count=1,
        alignment_delta_ms=0,
        quality=StreamQualitySummary(
            raw_sample_count=1,
            clean_sample_count=1,
            dropped_sample_count=0,
        ),
        clean_samples=[
            CleanSample(
                sample_index=0,
                raw_offset_ms=0,
                aligned_offset_ms=0,
                timestamp_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
                aligned_timestamp_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
                values={"hr_bpm": 80},
            )
        ],
    )

    payload = stream.model_dump(mode="json")
    assert "clean_samples" not in payload
