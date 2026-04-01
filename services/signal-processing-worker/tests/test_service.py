from __future__ import annotations

from datetime import datetime, timezone

from signal_processing_worker.models import RawSample, RawStreamDescriptor
from signal_processing_worker.service import SignalProcessingService


def _service() -> SignalProcessingService:
    service = SignalProcessingService(
        database=None,  # type: ignore[arg-type]
        storage=None,  # type: ignore[arg-type]
        clean_root_prefix="clean-sessions",
        preprocessing_version="e1-v1",
        gap_factor=1.8,
        max_samples_per_stream=10000,
        persist_outputs=False,
    )

    original_extract = service._extract_stream_features

    def _extract_stream_features_compat(*, stream_name, clean_samples):
        result = original_extract(stream_name=stream_name, clean_samples=clean_samples)
        if isinstance(result, tuple) and len(result) == 2:
            windows, summary = result
            return windows, summary, {}
        return result

    service._extract_stream_features = _extract_stream_features_compat  # type: ignore[method-assign]
    return service


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


def test_feature_windows_are_extracted_for_numeric_streams() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-hr",
        device_id="polar-1",
        stream_name="polar_hr",
        stream_kind="timeseries",
        sample_count=5,
        file_ref="streams/polar_hr/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"hr_bpm": 80}),
        RawSample(sample_index=1, offset_ms=5000, values={"hr_bpm": 82}),
        RawSample(sample_index=2, offset_ms=10000, values={"hr_bpm": 85}),
        RawSample(sample_index=3, offset_ms=15000, values={"hr_bpm": 87}),
        RawSample(sample_index=4, offset_ms=20000, values={"hr_bpm": 90}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    assert processed.feature_summary is not None
    assert processed.feature_summary.window_count >= 2
    assert "hr_bpm__mean" in processed.feature_summary.feature_names
    assert processed.feature_windows[0].values["sample_count"] >= 1


def test_feature_windows_capture_activity_mode_for_context_streams() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-watch-ctx",
        device_id="watch-1",
        stream_name="watch_activity_context",
        stream_kind="timeseries",
        sample_count=4,
        file_ref="streams/watch_activity_context/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"activity_label": "walk", "confidence": 0.7}),
        RawSample(sample_index=1, offset_ms=10000, values={"activity_label": "walk", "confidence": 0.9}),
        RawSample(sample_index=2, offset_ms=20000, values={"activity_label": "stand", "confidence": 0.8}),
        RawSample(sample_index=3, offset_ms=30000, values={"activity_label": "walk", "confidence": 0.8}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    assert processed.feature_summary is not None
    assert "activity_label__mode" in processed.feature_summary.feature_names
    modes = [window.values.get("activity_label__mode") for window in processed.feature_windows]
    assert "walk" in modes


def test_rr_stream_includes_extended_hrv_features() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-rr",
        device_id="polar-1",
        stream_name="polar_rr",
        stream_kind="timeseries",
        sample_count=8,
        file_ref="streams/polar_rr/samples.csv.gz",
    )

    rr_values = [812, 804, 798, 790, 802, 808, 796, 788]
    raw_samples = [
        RawSample(sample_index=index, offset_ms=index * 1000, values={"rr_ms": value})
        for index, value in enumerate(rr_values)
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    first_window = processed.feature_windows[0].values
    assert "rr_like__sdnn" in first_window
    assert "rr_like__nn50" in first_window
    assert "rr_like__pnn20" in first_window
    assert "rr_like__sd1" in first_window
    assert "rr_like__sd2" in first_window
    assert "rr_like__triangular_index" in first_window
    assert "rr_like__sample_entropy_m2_r02" in first_window
    assert "rr_like__lf_power" in first_window
    assert "rr_like__hf_power" in first_window
    assert "rr_like__lf_hf_ratio" in first_window
    assert first_window["rr_like__valid_count"] >= 2


def test_ecg_stream_includes_quality_features() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-ecg",
        device_id="polar-1",
        stream_name="polar_ecg",
        stream_kind="timeseries",
        sample_count=8,
        file_ref="streams/polar_ecg/samples.csv.gz",
    )

    ecg_values = [100, 300, 150, -50, 400, 120, -80, 260]
    raw_samples = [
        RawSample(sample_index=index, offset_ms=index * 8, values={"voltage_uv": value})
        for index, value in enumerate(ecg_values)
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    first_window = processed.feature_windows[0].values
    assert first_window["ecg_sample_count"] >= 1
    assert "ecg_coverage_ratio" in first_window
    assert "ecg_peak_count" in first_window
    assert "ecg_noise_ratio" in first_window


def test_polar_acc_stream_includes_motion_features() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-acc",
        device_id="polar-1",
        stream_name="polar_acc",
        stream_kind="timeseries",
        sample_count=5,
        file_ref="streams/polar_acc/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"acc_x_mg": 10, "acc_y_mg": 20, "acc_z_mg": 980}),
        RawSample(sample_index=1, offset_ms=20, values={"acc_x_mg": 200, "acc_y_mg": 120, "acc_z_mg": 1100}),
        RawSample(sample_index=2, offset_ms=40, values={"acc_x_mg": 500, "acc_y_mg": 300, "acc_z_mg": 1300}),
        RawSample(sample_index=3, offset_ms=60, values={"acc_x_mg": 100, "acc_y_mg": 80, "acc_z_mg": 950}),
        RawSample(sample_index=4, offset_ms=80, values={"acc_x_mg": 700, "acc_y_mg": 200, "acc_z_mg": 1500}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    first_window = processed.feature_windows[0].values
    assert "polar_acc__energy" in first_window
    assert "polar_acc__jerk_mean" in first_window
    assert "polar_acc__stationary_ratio" in first_window
    assert "polar_acc__motion_burst_count" in first_window


def test_p2_selector_polar_cardio_family_excludes_non_cardio_features() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-rr-selector",
        device_id="polar-1",
        stream_name="polar_rr",
        stream_kind="timeseries",
        sample_count=6,
        file_ref="streams/polar_rr/samples.csv.gz",
    )

    rr_values = [810, 802, 796, 804, 798, 792]
    raw_samples = [
        RawSample(sample_index=index, offset_ms=index * 1000, values={"rr_ms": value})
        for index, value in enumerate(rr_values)
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    feature_names = set(processed.feature_summary.feature_names if processed.feature_summary else [])
    assert "rr_like__sdnn" in feature_names
    assert not any(name.startswith("ecg_") for name in feature_names)
    assert not any(name.startswith("polar_acc__") for name in feature_names)
    assert not any(name.startswith("acc_mag__") for name in feature_names)


def test_p2_selector_watch_motion_family_excludes_cardio_features() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-watch-acc-selector",
        device_id="watch-1",
        stream_name="watch_accelerometer",
        stream_kind="timeseries",
        sample_count=5,
        file_ref="streams/watch_accelerometer/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"acc_x_g": 0.02, "acc_y_g": 0.04, "acc_z_g": 1.01}),
        RawSample(sample_index=1, offset_ms=20, values={"acc_x_g": 0.10, "acc_y_g": 0.02, "acc_z_g": 1.10}),
        RawSample(sample_index=2, offset_ms=40, values={"acc_x_g": 0.30, "acc_y_g": 0.20, "acc_z_g": 1.35}),
        RawSample(sample_index=3, offset_ms=60, values={"acc_x_g": 0.08, "acc_y_g": 0.03, "acc_z_g": 0.98}),
        RawSample(sample_index=4, offset_ms=80, values={"acc_x_g": 0.25, "acc_y_g": 0.10, "acc_z_g": 1.20}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    first_window = processed.feature_windows[0].values
    assert "acc_mag__mean" in first_window
    assert "rr_like__sdnn" not in first_window
    assert "ecg_sample_count" not in first_window


def test_p2_quality_gated_export_drops_noisy_rr_samples_before_feature_export() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-rr-gate",
        device_id="polar-1",
        stream_name="polar_rr",
        stream_kind="timeseries",
        sample_count=4,
        file_ref="streams/polar_rr/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"rr_ms": 820}),
        RawSample(sample_index=1, offset_ms=1000, values={"rr_ms": 3000}),  # out of range -> dropped
        RawSample(sample_index=2, offset_ms=2000, values={"rr_ms": 790}),
        RawSample(sample_index=3, offset_ms=3000, values={"rr_ms": 805}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    assert processed.quality.noisy_sample_count == 1
    assert processed.clean_sample_count == 3
    assert all(sample.values["rr_ms"] <= 2500 for sample in processed.clean_samples)
    assert processed.feature_windows[0].values["rr_like__valid_count"] == 3


def test_p2_quality_gate_marks_stream_when_all_rr_samples_are_rejected() -> None:
    service = _service()
    descriptor = RawStreamDescriptor(
        stream_id="s-polar-rr-empty-gate",
        device_id="polar-1",
        stream_name="polar_rr",
        stream_kind="timeseries",
        sample_count=3,
        file_ref="streams/polar_rr/samples.csv.gz",
    )

    raw_samples = [
        RawSample(sample_index=0, offset_ms=0, values={"rr_ms": 2800}),
        RawSample(sample_index=1, offset_ms=1000, values={"rr_ms": 3000}),
        RawSample(sample_index=2, offset_ms=2000, values={"rr_ms": 2700}),
    ]

    processed = service._process_stream_samples(
        descriptor=descriptor,
        session_started_at_utc=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        raw_samples=raw_samples,
    )

    assert processed.clean_sample_count == 0
    assert processed.quality.noisy_sample_count == 3
    assert processed.feature_summary is not None
    assert processed.feature_summary.window_count == 0
    assert "all samples were dropped during cleaning" in processed.quality.warnings
    assert "no clean samples available for feature extraction" in processed.feature_summary.warnings
