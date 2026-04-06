from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional


class StreamBuffer:
    def __init__(
        self,
        window_size_ms: int,
        step_size_ms: int,
        max_samples_per_stream: int = 50000,
        max_heart_staleness_ms: int = 30000,
        final_heart_staleness_ms: int | None = None,
    ) -> None:
        self._window_size_ms = window_size_ms
        self._step_size_ms = step_size_ms
        self._max_samples = max_samples_per_stream
        self._max_heart_staleness_ms = max_heart_staleness_ms
        self._final_heart_staleness_ms = (
            final_heart_staleness_ms
            if final_heart_staleness_ms is not None
            else max(max_heart_staleness_ms, window_size_ms * 10)
        )
        self._streams: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
        self._last_emit_offset: int = -step_size_ms - 1

    def reset(self) -> None:
        self._streams.clear()
        self._last_emit_offset = -self._step_size_ms - 1

    def add(self, stream_name: str, offset_ms: int, values: dict[str, Any]) -> None:
        samples = self._streams[stream_name]
        samples.append((offset_ms, values))
        samples.sort(key=lambda x: x[0])
        if len(samples) > self._max_samples:
            cutoff = samples[-self._max_samples][0]
            self._streams[stream_name] = [(o, v) for o, v in samples if o >= cutoff]

    def try_emit_window(
        self,
    ) -> Optional[
        tuple[
            int,
            int,
            str,
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
        ]
    ]:
        return self._emit_window(force=False)

    def try_emit_final_window(
        self,
    ) -> Optional[
        tuple[
            int,
            int,
            str,
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
        ]
    ]:
        return self._emit_window(force=True)

    def peek_emit_block_reason(self) -> str | None:
        if not self._streams.get("watch_accelerometer"):
            return "no_accelerometer_stream"
        heart_stream_name = self._resolve_heart_stream_name()
        if heart_stream_name is None:
            return "no_heart_stream"
        acc = self._streams["watch_accelerometer"]
        hr = self._streams[heart_stream_name]
        if not acc:
            return "no_accelerometer_samples"
        if not hr:
            return "no_heart_samples"
        max_offset = acc[-1][0]
        window_end = max_offset
        window_start = window_end - self._window_size_ms
        if window_start < 0:
            return "insufficient_timeline"
        if window_end <= self._last_emit_offset + self._step_size_ms:
            return "step_backoff"
        acc_in_window = [(o, v) for o, v in acc if window_start <= o < window_end]
        hr_in_window = self._heart_samples_for_window(hr=hr, window_start=window_start, window_end=window_end)
        if not acc_in_window:
            return "no_accelerometer_in_window"
        if not hr_in_window:
            return "heart_stale_or_missing"
        return None

    def _emit_window(
        self,
        *,
        force: bool,
    ) -> Optional[
        tuple[
            int,
            int,
            str,
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
            list[tuple[int, dict[str, Any]]],
        ]
    ]:
        if not self._streams.get("watch_accelerometer"):
            return None
        heart_stream_name = self._resolve_heart_stream_name()
        if heart_stream_name is None:
            return None
        acc = self._streams["watch_accelerometer"]
        hr = self._streams[heart_stream_name]
        if not acc or not hr:
            return None
        max_offset = acc[-1][0]
        window_end = max_offset
        window_start = window_end - self._window_size_ms
        if window_start < 0:
            return None
        if not force and window_end <= self._last_emit_offset + self._step_size_ms:
            return None
        acc_in_window = [(o, v) for o, v in acc if window_start <= o < window_end]
        staleness = self._final_heart_staleness_ms if force else self._max_heart_staleness_ms
        hr_in_window = self._heart_samples_for_window(
            hr=hr,
            window_start=window_start,
            window_end=window_end,
            max_staleness_ms=staleness,
        )
        rr_in_window = self._rr_samples_for_window(
            window_start=window_start,
            window_end=window_end,
            max_staleness_ms=staleness,
        )
        activity_ctx_in_window = self._optional_stream_samples_for_window(
            "watch_activity_context",
            window_start=window_start,
            window_end=window_end,
            max_staleness_ms=staleness,
        )
        if not acc_in_window or not hr_in_window:
            return None
        self._last_emit_offset = window_end
        return (
            window_start,
            window_end,
            heart_stream_name,
            acc_in_window,
            hr_in_window,
            rr_in_window,
            activity_ctx_in_window,
        )

    def _resolve_heart_stream_name(self) -> Optional[str]:
        # Polar is the preferred cardio source in fusion-first runtime.
        if self._streams.get("polar_hr"):
            return "polar_hr"
        if self._streams.get("watch_heart_rate"):
            return "watch_heart_rate"
        return None

    def _heart_samples_for_window(
        self,
        *,
        hr: list[tuple[int, dict[str, Any]]],
        window_start: int,
        window_end: int,
        max_staleness_ms: int | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        budget = self._max_heart_staleness_ms if max_staleness_ms is None else max_staleness_ms
        in_window = [(o, v) for o, v in hr if window_start <= o < window_end]
        if in_window:
            return in_window
        fallback = next(((o, v) for o, v in reversed(hr) if o < window_end), None)
        if fallback is None:
            return []
        sample_offset, sample_values = fallback
        if window_end - sample_offset > budget:
            return []
        return [(sample_offset, sample_values)]

    def _rr_samples_for_window(
        self,
        *,
        window_start: int,
        window_end: int,
        max_staleness_ms: int | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        budget = self._max_heart_staleness_ms if max_staleness_ms is None else max_staleness_ms
        rr = self._streams.get("polar_rr")
        if not rr:
            return []
        in_window = [(o, v) for o, v in rr if window_start <= o < window_end]
        if in_window:
            return in_window
        fallback = next(((o, v) for o, v in reversed(rr) if o < window_end), None)
        if fallback is None:
            return []
        sample_offset, sample_values = fallback
        if window_end - sample_offset > budget:
            return []
        return [(sample_offset, sample_values)]

    def _optional_stream_samples_for_window(
        self,
        stream_name: str,
        *,
        window_start: int,
        window_end: int,
        max_staleness_ms: int | None = None,
    ) -> list[tuple[int, dict[str, Any]]]:
        budget = self._max_heart_staleness_ms if max_staleness_ms is None else max_staleness_ms
        stream = self._streams.get(stream_name)
        if not stream:
            return []
        in_window = [(o, v) for o, v in stream if window_start <= o < window_end]
        if in_window:
            return in_window
        fallback = next(((o, v) for o, v in reversed(stream) if o < window_end), None)
        if fallback is None:
            return []
        sample_offset, sample_values = fallback
        if window_end - sample_offset > budget:
            return []
        return [(sample_offset, sample_values)]
