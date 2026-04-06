from __future__ import annotations

import math
from typing import Any

_HR_BPM_FEATURE_KEYS = frozenset(
    {
        "watch_bvp_c0__mean",
        "watch_bvp_c0__last",
        "watch_bvp_c0__min",
        "watch_bvp_c0__max",
        "watch_bvp_c0__std",
        "chest_ecg_c0__mean",
        "chest_ecg_c0__last",
        "chest_ecg_c0__min",
        "chest_ecg_c0__max",
        "chest_ecg_c0__std",
        "chest_rr_hr_mean",
        "chest_rr_hr_std",
        "chest_rr_hr_min",
        "chest_rr_hr_max",
    }
)


def _finite(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _range_stat_sigma(rs: dict[str, Any]) -> float | None:
    p10 = _finite(rs.get("p10"))
    p90 = _finite(rs.get("p90"))
    if p10 is None or p90 is None:
        return None
    spread = p90 - p10
    if spread <= 0:
        return None
    return max(spread / 2.5633312, 1e-3)


def _range_stat_median(rs: dict[str, Any]) -> float | None:
    m = _finite(rs.get("median"))
    return m


def _z(x: float, mu: float, sigma: float) -> float:
    return (x - mu) / max(sigma, 1e-9)


def apply_physiology_baseline_l1(
    features: dict[str, float],
    physiology_baseline: dict[str, Any],
) -> tuple[dict[str, float], dict[str, Any]]:
    meta: dict[str, Any] = {"applied": False, "adjusted_keys": []}
    if not physiology_baseline:
        return features, meta

    out = dict(features)
    mu_map = physiology_baseline.get("l1_feature_mu")
    sigma_map = physiology_baseline.get("l1_feature_sigma")
    if isinstance(mu_map, dict) and isinstance(sigma_map, dict):
        for name, mu_raw in mu_map.items():
            if not isinstance(name, str) or name not in out:
                continue
            mu = _finite(mu_raw)
            sig = _finite(sigma_map.get(name))
            if mu is None or sig is None or sig <= 0:
                continue
            out[name] = round(_z(out[name], mu, sig), 6)
            meta["adjusted_keys"].append(name)
        if meta["adjusted_keys"]:
            meta["applied"] = True
            meta["basis"] = "l1_feature_mu_sigma"
            return out, meta

    basis_parts: list[str] = []

    resting = physiology_baseline.get("resting_hr_bpm")
    if isinstance(resting, dict):
        mu = _range_stat_median(resting)
        sigma = _range_stat_sigma(resting)
        if mu is not None and sigma is not None:
            hr_keys: list[str] = []
            for k in _HR_BPM_FEATURE_KEYS:
                if k not in out:
                    continue
                out[k] = round(_z(out[k], mu, sigma), 6)
                hr_keys.append(k)
            if hr_keys:
                meta["adjusted_keys"].extend(hr_keys)
                meta["applied"] = True
                basis_parts.append("resting_hr_bpm")

    rmssd_rs = physiology_baseline.get("hrv_rmssd_ms")
    if isinstance(rmssd_rs, dict):
        mu = _range_stat_median(rmssd_rs)
        sigma = _range_stat_sigma(rmssd_rs)
        if mu is not None and sigma is not None and "chest_rr_rmssd" in out:
            out["chest_rr_rmssd"] = round(_z(out["chest_rr_rmssd"], mu, sigma), 6)
            meta["adjusted_keys"].append("chest_rr_rmssd")
            meta["applied"] = True
            basis_parts.append("hrv_rmssd_ms")

    sdnn_rs = physiology_baseline.get("hrv_sdnn_ms")
    if isinstance(sdnn_rs, dict):
        mu = _range_stat_median(sdnn_rs)
        sigma = _range_stat_sigma(sdnn_rs)
        if mu is not None and sigma is not None and "chest_rr_sdnn" in out:
            out["chest_rr_sdnn"] = round(_z(out["chest_rr_sdnn"], mu, sigma), 6)
            meta["adjusted_keys"].append("chest_rr_sdnn")
            meta["applied"] = True
            basis_parts.append("hrv_sdnn_ms")

    if basis_parts:
        meta["basis"] = "+".join(basis_parts)

    return out, meta
