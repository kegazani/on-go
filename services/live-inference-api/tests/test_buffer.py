from __future__ import annotations

from live_inference_api.buffer import StreamBuffer


def test_try_emit_window_prefers_polar_hr_when_available() -> None:
    buffer = StreamBuffer(window_size_ms=15000, step_size_ms=5000)
    for i in range(0, 20000, 1000):
        buffer.add("watch_accelerometer", i, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})
        buffer.add("watch_heart_rate", i, {"hr_bpm": 65.0})
        buffer.add("polar_hr", i, {"hr_bpm": 75.0})

    result = buffer.try_emit_window()

    assert result is not None
    _, _, heart_source, _, hr, _, _ = result
    assert heart_source == "polar_hr"
    assert hr
    assert all(sample["hr_bpm"] == 75.0 for _, sample in hr)


def test_try_emit_window_uses_recent_heart_fallback_when_hr_sparse() -> None:
    buffer = StreamBuffer(window_size_ms=15000, step_size_ms=5000, max_heart_staleness_ms=30000)

    # Dense accelerometer stream, sparse heart updates.
    for i in range(0, 45000, 1000):
        buffer.add("watch_accelerometer", i, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})
    buffer.add("watch_heart_rate", 22000, {"hr_bpm": 65.0})

    first = buffer.try_emit_window()
    assert first is not None
    _, first_end, _, _, first_hr, _, _ = first
    assert first_end == 44000
    assert first_hr == [(22000, {"hr_bpm": 65.0})]

    # New accelerometer data should allow next window emit even without new HR.
    for i in range(45000, 52000, 1000):
        buffer.add("watch_accelerometer", i, {"acc_x_g": 0.2, "acc_y_g": 0.1, "acc_z_g": 1.1})
    second = buffer.try_emit_window()
    assert second is not None
    _, second_end, _, _, second_hr, _, _ = second
    assert second_end == 51000
    assert second_hr == [(22000, {"hr_bpm": 65.0})]


def test_try_emit_window_allows_stale_heart_within_extended_staleness_budget() -> None:
    buffer = StreamBuffer(window_size_ms=15000, step_size_ms=5000, max_heart_staleness_ms=120000)

    for i in range(0, 60000, 1000):
        buffer.add("watch_accelerometer", i, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})
    buffer.add("watch_heart_rate", 10000, {"hr_bpm": 65.0})

    assert buffer.try_emit_window() is not None

    for i in range(60000, 72000, 1000):
        buffer.add("watch_accelerometer", i, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})
    assert buffer.try_emit_window() is not None


def test_try_emit_window_blocks_when_heart_sample_is_too_old() -> None:
    buffer = StreamBuffer(window_size_ms=15000, step_size_ms=5000, max_heart_staleness_ms=10000)

    for i in range(0, 60000, 1000):
        buffer.add("watch_accelerometer", i, {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0})
    buffer.add("watch_heart_rate", 10000, {"hr_bpm": 65.0})

    # Latest HR is older than allowed staleness for current window end.
    assert buffer.try_emit_window() is None
