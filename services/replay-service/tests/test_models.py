from __future__ import annotations

from replay_service.models import ReplayWindowRequest


def test_realtime_mode_requires_speed_one() -> None:
    try:
        ReplayWindowRequest.model_validate(
            {
                "mode": "realtime",
                "speed_multiplier": 2.0,
            }
        )
    except Exception as exc:
        assert "speed_multiplier must be 1.0" in str(exc)
        return

    raise AssertionError("Validation should fail for realtime mode with speed_multiplier != 1.0")


def test_stream_names_must_be_unique() -> None:
    try:
        ReplayWindowRequest.model_validate(
            {
                "mode": "accelerated",
                "speed_multiplier": 2.0,
                "stream_names": ["watch_heart_rate", "watch_heart_rate"],
            }
        )
    except Exception as exc:
        assert "stream_names values must be unique" in str(exc)
        return

    raise AssertionError("Validation should fail for duplicate stream_names")
