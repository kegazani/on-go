from __future__ import annotations

from live_inference_api.baseline_l1 import apply_physiology_baseline_l1


def test_apply_l1_resting_hr_zscores_hr_features() -> None:
    sigma = (70.0 - 50.0) / 2.5633312
    features = {
        "chest_ecg_c0__mean": 72.0,
        "watch_acc_mag__mean": 1.0,
    }
    base = {"resting_hr_bpm": {"median": 60.0, "p10": 50.0, "p90": 70.0, "sample_count": 10}}
    out, meta = apply_physiology_baseline_l1(features, base)
    assert meta["applied"] is True
    assert "resting_hr_bpm" in meta["basis"]
    assert abs(out["chest_ecg_c0__mean"] - (72.0 - 60.0) / sigma) < 1e-5
    assert out["watch_acc_mag__mean"] == 1.0


def test_apply_l1_explicit_mu_sigma_takes_precedence() -> None:
    features = {"chest_ecg_c0__mean": 80.0, "other": 1.0}
    base = {
        "l1_feature_mu": {"chest_ecg_c0__mean": 70.0, "other": 0.0},
        "l1_feature_sigma": {"chest_ecg_c0__mean": 5.0, "other": 2.0},
        "resting_hr_bpm": {"median": 60.0, "p10": 50.0, "p90": 90.0, "sample_count": 3},
    }
    out, meta = apply_physiology_baseline_l1(features, base)
    assert meta["basis"] == "l1_feature_mu_sigma"
    assert out["chest_ecg_c0__mean"] == 2.0
    assert out["other"] == 0.5


def test_apply_l1_noop_when_empty_baseline() -> None:
    features = {"chest_ecg_c0__mean": 72.0}
    out, meta = apply_physiology_baseline_l1(features, {})
    assert out is features
    assert meta["applied"] is False
