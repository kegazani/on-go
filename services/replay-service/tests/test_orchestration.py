from __future__ import annotations

from types import SimpleNamespace

from replay_service.models import ReplayWindowRequest, ReplayWindowResponse
from replay_service.service import ReplayService


class _DummyStorage:
    pass


def _service() -> ReplayService:
    return ReplayService(
        database=None,  # type: ignore[arg-type]
        storage=_DummyStorage(),  # type: ignore[arg-type]
        default_window_ms=5000,
        max_window_ms=600000,
        max_samples_per_stream=2000,
    )


def test_iterate_windows_single_window_mode(monkeypatch) -> None:
    service = _service()

    monkeypatch.setattr(service, "get_manifest", lambda session_id: SimpleNamespace(duration_ms=6000))
    monkeypatch.setattr(
        service,
        "get_window",
        lambda session_id, request: ReplayWindowResponse(
            session_id=session_id,
            mode=request.mode,
            speed_multiplier=request.speed_multiplier,
            from_offset_ms=request.from_offset_ms,
            to_offset_ms=request.from_offset_ms + 1000,
            next_offset_ms=request.from_offset_ms + 1000,
            stream_names=["watch_heart_rate"],
            sample_count=1,
            event_count=0,
            samples=[],
            events=[],
            warnings=[],
        ),
    )

    request = ReplayWindowRequest.model_validate(
        {
            "mode": "realtime",
            "speed_multiplier": 1.0,
            "from_offset_ms": 0,
            "window_ms": 1000,
            "stream_names": ["watch_heart_rate"],
            "include_events": False,
            "max_samples_per_stream": 10,
        }
    )
    windows, duration = service.iterate_windows(
        session_id="session-001",
        request=request,
        orchestration_mode="single_window",
    )

    assert duration == 6000
    assert len(windows) == 1
    assert windows[0].from_offset_ms == 0


def test_iterate_windows_full_session_mode(monkeypatch) -> None:
    service = _service()

    monkeypatch.setattr(service, "get_manifest", lambda session_id: SimpleNamespace(duration_ms=2500))

    def _fake_get_window(session_id, request):
        to_offset = min(request.from_offset_ms + request.window_ms, 2500)
        return ReplayWindowResponse(
            session_id=session_id,
            mode=request.mode,
            speed_multiplier=request.speed_multiplier,
            from_offset_ms=request.from_offset_ms,
            to_offset_ms=to_offset,
            next_offset_ms=to_offset,
            stream_names=["watch_heart_rate"],
            sample_count=1,
            event_count=0,
            samples=[],
            events=[],
            warnings=[],
        )

    monkeypatch.setattr(service, "get_window", _fake_get_window)

    request = ReplayWindowRequest.model_validate(
        {
            "mode": "realtime",
            "speed_multiplier": 1.0,
            "from_offset_ms": 0,
            "window_ms": 1000,
            "stream_names": ["watch_heart_rate"],
            "include_events": False,
            "max_samples_per_stream": 10,
        }
    )
    windows, duration = service.iterate_windows(
        session_id="session-001",
        request=request,
        orchestration_mode="full_session",
    )

    assert duration == 2500
    assert [window.from_offset_ms for window in windows] == [0, 1000, 2000]
    assert windows[-1].to_offset_ms == 2500
