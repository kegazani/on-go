from __future__ import annotations

from replay_service.errors import ValidationError
from replay_service.models import ReplayStreamDescriptor
from replay_service.service import ReplayService


class _StubStorage:
    def __init__(self, payload_by_key: dict[str, str]) -> None:
        self._payload_by_key = payload_by_key

    def read_text(self, object_key: str) -> str:
        return self._payload_by_key[object_key]


def _service_with_payload(payload_by_key: dict[str, str]) -> ReplayService:
    return ReplayService(
        database=None,  # type: ignore[arg-type]
        storage=_StubStorage(payload_by_key),  # type: ignore[arg-type]
        default_window_ms=5000,
        max_window_ms=600000,
        max_samples_per_stream=2000,
    )


def _stream_descriptor(object_key: str) -> ReplayStreamDescriptor:
    return ReplayStreamDescriptor(
        stream_id="stream-1",
        device_id="watch-1",
        stream_name="watch_heart_rate",
        stream_kind="timeseries",
        sample_count=3,
        started_at_utc="2026-03-21T10:00:00Z",
        ended_at_utc="2026-03-21T10:00:03Z",
        file_ref="streams/watch_heart_rate/samples.csv",
        sample_object_key=object_key,
        sample_content_type="text/csv",
        sample_upload_status="verified",
        checksum_sha256="a" * 64,
        available_for_replay=True,
    )


def test_load_stream_window_samples_for_accelerated_mode() -> None:
    service = _service_with_payload(
        {
            "streams/watch_heart_rate/samples.csv": "\n".join(
                [
                    "sample_index,offset_ms,timestamp_utc,hr_bpm",
                    "0,0,2026-03-21T10:00:00Z,80",
                    "1,1000,2026-03-21T10:00:01Z,82",
                    "2,2000,2026-03-21T10:00:02Z,84",
                ]
            )
        }
    )

    samples, truncated = service._load_stream_window_samples(
        stream=_stream_descriptor("streams/watch_heart_rate/samples.csv"),
        from_offset_ms=500,
        to_offset_ms=2000,
        mode="accelerated",
        speed_multiplier=2.0,
        max_samples=10,
    )

    assert truncated is False
    assert [sample.offset_ms for sample in samples] == [1000, 2000]
    assert [sample.replay_at_offset_ms for sample in samples] == [750, 1250]
    assert [sample.values["hr_bpm"] for sample in samples] == [82, 84]


def test_load_stream_window_samples_requires_offset_column() -> None:
    service = _service_with_payload(
        {
            "streams/watch_heart_rate/samples.csv": "\n".join(
                [
                    "sample_index,timestamp_utc,hr_bpm",
                    "0,2026-03-21T10:00:00Z,80",
                ]
            )
        }
    )

    try:
        service._load_stream_window_samples(
            stream=_stream_descriptor("streams/watch_heart_rate/samples.csv"),
            from_offset_ms=0,
            to_offset_ms=1000,
            mode="realtime",
            speed_multiplier=1.0,
            max_samples=10,
        )
    except ValidationError as exc:
        assert exc.code == "replay_missing_offset_ms"
        return

    raise AssertionError("Expected ValidationError for missing offset_ms column")
