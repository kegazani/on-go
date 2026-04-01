from __future__ import annotations

from datetime import datetime, timezone

from signal_processing_worker.models import (
    CleanSample,
    FeatureWindow,
    OffsetInterval,
    ProcessedStream,
    StreamFeatureSummary,
    StreamQualitySummary,
)


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


def test_feature_window_requires_order() -> None:
    try:
        FeatureWindow.model_validate(
            {
                "window_index": 0,
                "started_offset_ms": 500,
                "ended_offset_ms": 100,
                "sample_count": 2,
                "values": {"hr_bpm__mean": 82},
            }
        )
    except Exception as exc:
        assert "ended_offset_ms must be >= started_offset_ms" in str(exc)
        return

    raise AssertionError("Validation should fail when ended_offset_ms < started_offset_ms")


def test_processed_stream_excludes_runtime_feature_windows_from_dump() -> None:
    stream = ProcessedStream(
        stream_name="polar_hr",
        stream_id="stream-1",
        device_id="polar-1",
        raw_sample_count=4,
        clean_sample_count=4,
        alignment_delta_ms=0,
        quality=StreamQualitySummary(
            raw_sample_count=4,
            clean_sample_count=4,
            dropped_sample_count=0,
        ),
        feature_windows=[
            FeatureWindow(
                window_index=0,
                started_offset_ms=0,
                ended_offset_ms=5000,
                sample_count=4,
                values={"hr_bpm__mean": 81.5},
            )
        ],
        feature_summary=StreamFeatureSummary(
            window_size_ms=5000,
            step_size_ms=2500,
            window_count=1,
            feature_names=["hr_bpm__mean"],
        ),
    )

    payload = stream.model_dump(mode="json")
    assert "feature_windows" not in payload
