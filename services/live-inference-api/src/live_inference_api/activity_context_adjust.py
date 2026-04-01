from __future__ import annotations

from collections import Counter
from typing import Any

_REST_LABELS = frozenset({"seated_rest", "standing_rest", "baseline", "rest", "stationary", "idle"})
_KNOWN_TYPES = frozenset({"rest", "light_motion", "high_motion"})
_MIN_LABELED_SAMPLES = 2
_MOTION_FRACTION_THRESHOLD = 0.35


def _normalize_token(raw: object) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in _KNOWN_TYPES:
        return s
    return None


def _extract_activity_type(sample: dict[str, Any]) -> str | None:
    for key in ("activity_type", "activityType", "ActivityType"):
        if key in sample:
            return _normalize_token(sample.get(key))
    return None


def motion_level_for_sample(sample: dict[str, Any]) -> float | None:
    t = _extract_activity_type(sample)
    if t is None:
        return None
    if t == "rest":
        return 0.0
    if t == "light_motion":
        return 1.0
    if t == "high_motion":
        return 2.0
    return None


def motion_levels_for_samples(samples: list[dict[str, Any]] | None) -> list[float]:
    if not samples:
        return []
    out: list[float] = []
    for s in samples:
        m = motion_level_for_sample(s)
        if m is not None:
            out.append(m)
    return out


def adjust_activity_label_for_context(
    ml_label: str,
    context_samples: list[dict[str, Any]] | None,
) -> str:
    if not context_samples:
        return ml_label
    tokens: list[str] = []
    for s in context_samples:
        t = _extract_activity_type(s)
        if t is not None:
            tokens.append(t)
    if len(tokens) < _MIN_LABELED_SAMPLES:
        return ml_label
    counts = Counter(tokens)
    rest_c = int(counts.get("rest", 0))
    light_c = int(counts.get("light_motion", 0))
    high_c = int(counts.get("high_motion", 0))
    total = rest_c + light_c + high_c
    if total == 0:
        return ml_label
    motion_c = light_c + high_c
    motion_fraction = motion_c / total
    mode = counts.most_common(1)[0][0]
    ml_norm = str(ml_label or "").strip().lower()
    if ml_norm not in _REST_LABELS:
        return ml_label
    if mode == "high_motion":
        return "light_exercise"
    if mode == "light_motion":
        return "walking"
    if mode == "rest" and motion_fraction >= _MOTION_FRACTION_THRESHOLD:
        if high_c >= light_c and high_c > 0:
            return "light_exercise"
        return "walking"
    return ml_label
