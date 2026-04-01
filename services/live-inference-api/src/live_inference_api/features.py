from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Optional

from live_inference_api.activity_context_adjust import motion_levels_for_samples

_LEGACY_ZERO_FEATURES = (
    "watch_acc_c0__last",
    "watch_acc_c0__max",
    "watch_acc_c0__mean",
    "watch_acc_c0__min",
    "watch_acc_c0__std",
    "watch_acc_c1__last",
    "watch_acc_c1__max",
    "watch_acc_c1__mean",
    "watch_acc_c1__min",
    "watch_acc_c1__std",
    "watch_acc_c2__last",
    "watch_acc_c2__max",
    "watch_acc_c2__mean",
    "watch_acc_c2__min",
    "watch_acc_c2__std",
    "watch_acc_mag__last",
    "watch_acc_mag__max",
    "watch_acc_mag__mean",
    "watch_acc_mag__min",
    "watch_acc_mag__std",
    "watch_bvp_c0__last",
    "watch_bvp_c0__max",
    "watch_bvp_c0__mean",
    "watch_bvp_c0__min",
    "watch_bvp_c0__std",
    "watch_eda_c0__last",
    "watch_eda_c0__max",
    "watch_eda_c0__mean",
    "watch_eda_c0__min",
    "watch_eda_c0__std",
    "watch_temp_c0__last",
    "watch_temp_c0__max",
    "watch_temp_c0__mean",
    "watch_temp_c0__min",
    "watch_temp_c0__std",
)


def extract_watch_features(
    acc_samples: list[dict[str, Any]],
    hr_samples: list[dict[str, Any]],
    rr_samples: list[dict[str, Any]] | None,
    window_duration_sec: float,
    sample_count: int,
    heart_source: str | None = None,
    manifest_layout: bool = False,
    activity_context_samples: list[dict[str, Any]] | None = None,
) -> dict[str, float]:
    features: dict[str, float]
    if manifest_layout:
        features = {}
    else:
        features = {
            "meta_segment_duration_sec": round(window_duration_sec, 6),
            "meta_source_sample_count": float(sample_count),
        }
        for name in _LEGACY_ZERO_FEATURES:
            features[name] = 0.0

    if acc_samples:
        x_vals: list[float] = []
        y_vals: list[float] = []
        z_vals: list[float] = []
        mags: list[float] = []
        for s in acc_samples:
            x, y, z = _f(s, "acc_x_g"), _f(s, "acc_y_g"), _f(s, "acc_z_g")
            if x is not None and y is not None and z is not None:
                x_vals.append(x)
                y_vals.append(y)
                z_vals.append(z)
                mags.append(math.sqrt(x * x + y * y + z * z))
        if x_vals:
            _add_channel_stats(features, "watch_acc_c0", x_vals)
            _add_channel_stats(features, "watch_acc_c1", y_vals)
            _add_channel_stats(features, "watch_acc_c2", z_vals)
        if mags:
            _add_channel_stats(features, "watch_acc_mag", mags)

    if hr_samples:
        hr_vals = []
        for sample in hr_samples:
            hr_val = _f(sample, "hr_bpm")
            if hr_val is not None:
                hr_vals.append(hr_val)
        if hr_vals:
            if manifest_layout:
                _add_channel_stats(features, "watch_bvp_c0", hr_vals)
                if heart_source == "polar_hr":
                    _add_channel_stats(features, "chest_ecg_c0", hr_vals)
                elif heart_source == "watch_heart_rate":
                    _add_channel_stats(features, "chest_ecg_c0", hr_vals)
            else:
                _add_channel_stats(features, "watch_bvp_c0", hr_vals)
                if heart_source == "polar_hr":
                    _add_channel_stats(features, "chest_ecg_c0", hr_vals)

    rr_vals = []
    for sample in rr_samples or []:
        rr_val = _f(sample, "rr_ms")
        if rr_val is not None:
            rr_vals.append(rr_val)
    if rr_vals and manifest_layout:
        _add_rr_proxy_stats(features, rr_vals)

    if manifest_layout:
        _add_fusion_proxy_stats(features)

    _add_activity_context_numeric_features(features, activity_context_samples)
    motion_levels = motion_levels_for_samples(activity_context_samples)
    if motion_levels:
        _add_channel_stats(features, "watch_activity_context_motion_level", motion_levels)

    return features


def _sanitize_key_part(key: str) -> str:
    return "".join(ch.lower() if ch.isalnum() or ch == "_" else "_" for ch in key.strip())


def _add_activity_context_numeric_features(
    features: dict[str, float],
    samples: list[dict[str, Any]] | None,
) -> None:
    if not samples:
        return
    key_vals: dict[str, list[float]] = {}
    for sample in samples:
        for k in sample:
            if not isinstance(k, str) or not k:
                continue
            fv = _f(sample, k)
            if fv is None:
                continue
            part = _sanitize_key_part(k)
            if not part:
                continue
            key_vals.setdefault(part, []).append(fv)
    for part, vals in key_vals.items():
        _add_channel_stats(features, f"watch_activity_context_{part}", vals)


def _f(sample: dict[str, Any], key: str) -> Optional[float]:
    v = sample.get(key)
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _add_channel_stats(features: dict[str, float], prefix: str, values: list[float]) -> None:
    if not values:
        return
    features[f"{prefix}__mean"] = round(mean(values), 6)
    features[f"{prefix}__std"] = round(pstdev(values), 6) if len(values) >= 2 else 0.0
    features[f"{prefix}__min"] = round(min(values), 6)
    features[f"{prefix}__max"] = round(max(values), 6)
    features[f"{prefix}__last"] = round(values[-1], 6)


def _add_rr_proxy_stats(features: dict[str, float], rr_vals: list[float]) -> None:
    if not rr_vals:
        return
    if len(rr_vals) == 1:
        v = rr_vals[0]
        hr_inst = 60000.0 / v if v > 0 else 0.0
        features.update(
            {
                "chest_rr_mean_nn": round(v, 6),
                "chest_rr_median_nn": round(v, 6),
                "chest_rr_min_nn": round(v, 6),
                "chest_rr_max_nn": round(v, 6),
                "chest_rr_sdnn": 0.0,
                "chest_rr_rmssd": 0.0,
                "chest_rr_sdsd": 0.0,
                "chest_rr_nn50": 0.0,
                "chest_rr_pnn50": 0.0,
                "chest_rr_iqr_nn": 0.0,
                "chest_rr_mad_nn": 0.0,
                "chest_rr_cvnn": 0.0,
                "chest_rr_cvsd": 0.0,
                "chest_rr_hr_mean": round(hr_inst, 6),
                "chest_rr_hr_std": 0.0,
                "chest_rr_hr_min": round(hr_inst, 6),
                "chest_rr_hr_max": round(hr_inst, 6),
                "polar_quality_rr_coverage_ratio": 1.0,
                "polar_quality_rr_valid_count": 1.0,
                "polar_quality_rr_outlier_ratio": 0.0,
            }
        )
        return
    rr_sorted = sorted(rr_vals)
    rr_diffs = [rr_vals[index] - rr_vals[index - 1] for index in range(1, len(rr_vals))]
    abs_diffs = [abs(delta) for delta in rr_diffs]
    mean_nn = mean(rr_vals)
    sdnn = pstdev(rr_vals) if len(rr_vals) >= 2 else 0.0
    rmssd = math.sqrt(sum(delta * delta for delta in rr_diffs) / len(rr_diffs)) if rr_diffs else 0.0
    sdsd = pstdev(rr_diffs) if len(rr_diffs) >= 2 else 0.0
    nn50 = float(sum(1 for delta in abs_diffs if delta > 50.0))
    pnn50 = (nn50 / len(abs_diffs) * 100.0) if abs_diffs else 0.0
    median_nn = rr_sorted[len(rr_sorted) // 2]
    iqr_nn = _percentile(rr_sorted, 75.0) - _percentile(rr_sorted, 25.0)
    mad_nn = median_abs = sorted(abs(item - median_nn) for item in rr_vals)[len(rr_vals) // 2]
    cvnn = (sdnn / mean_nn * 100.0) if mean_nn > 0 else 0.0
    cvsd = (rmssd / mean_nn * 100.0) if mean_nn > 0 else 0.0
    hr_vals = [60000.0 / value for value in rr_vals if value > 0]
    hr_mean = mean(hr_vals) if hr_vals else 0.0
    hr_std = pstdev(hr_vals) if len(hr_vals) >= 2 else 0.0

    features.update(
        {
            "chest_rr_mean_nn": round(mean_nn, 6),
            "chest_rr_median_nn": round(median_nn, 6),
            "chest_rr_min_nn": round(min(rr_vals), 6),
            "chest_rr_max_nn": round(max(rr_vals), 6),
            "chest_rr_sdnn": round(sdnn, 6),
            "chest_rr_rmssd": round(rmssd, 6),
            "chest_rr_sdsd": round(sdsd, 6),
            "chest_rr_nn50": round(nn50, 6),
            "chest_rr_pnn50": round(pnn50, 6),
            "chest_rr_iqr_nn": round(iqr_nn, 6),
            "chest_rr_mad_nn": round(mad_nn, 6),
            "chest_rr_cvnn": round(cvnn, 6),
            "chest_rr_cvsd": round(cvsd, 6),
            "chest_rr_hr_mean": round(hr_mean, 6),
            "chest_rr_hr_std": round(hr_std, 6),
            "chest_rr_hr_min": round(min(hr_vals), 6) if hr_vals else 0.0,
            "chest_rr_hr_max": round(max(hr_vals), 6) if hr_vals else 0.0,
            "polar_quality_rr_coverage_ratio": 1.0,
            "polar_quality_rr_valid_count": float(len(rr_vals)),
            "polar_quality_rr_outlier_ratio": 0.0,
        }
    )


def _add_fusion_proxy_stats(features: dict[str, float]) -> None:
    hr_mean = float(features.get("chest_rr_hr_mean", features.get("chest_ecg_c0__mean", 0.0)))
    hr_std = float(features.get("chest_rr_hr_std", features.get("chest_ecg_c0__std", 0.0)))
    acc_mean = float(features.get("watch_acc_mag__mean", 0.0))
    acc_std = float(features.get("watch_acc_mag__std", 0.0))
    features["fusion_hr_motion_mean_product"] = round(hr_mean * acc_mean, 6)
    features["fusion_hr_motion_std_product"] = round(hr_std * acc_std, 6)
    features["fusion_hr_motion_mean_ratio"] = round(hr_mean / (acc_mean + 1e-6), 6)
    features["fusion_hr_motion_std_ratio"] = round(hr_std / (acc_std + 1e-6), 6)
    features["fusion_hr_motion_mean_delta"] = round(hr_mean - acc_mean, 6)
    features["fusion_hr_motion_std_delta"] = round(hr_std - acc_std, 6)
    features["fusion_hr_motion_energy_proxy"] = round((hr_mean * hr_mean) + (acc_mean * acc_mean), 6)
    features["fusion_hr_motion_stability_proxy"] = round(1.0 / (1.0 + abs(hr_std - acc_std)), 6)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    pos = (q / 100.0) * (len(values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return values[lo]
    weight = pos - lo
    return values[lo] * (1.0 - weight) + values[hi] * weight
