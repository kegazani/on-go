from __future__ import annotations

from live_inference_api.calibration_l2 import apply_adaptation_l2


def test_l2_skips_when_level_none() -> None:
    pred = {"activity": "baseline", "arousal_coarse": "low", "valence_coarse": "neutral"}
    out, meta = apply_adaptation_l2(
        pred,
        {
            "active_personalization_level": "none",
            "l2_calibration": {"output_label_maps": {"arousal_coarse": {"low": "high"}}},
        },
    )
    assert out == pred
    assert meta["applied"] is False
    assert meta["reason"] == "level_skips_l2"


def test_l2_maps_when_light() -> None:
    pred = {"activity": "baseline", "arousal_coarse": "low", "valence_coarse": "neutral"}
    out, meta = apply_adaptation_l2(
        pred,
        {
            "active_personalization_level": "light",
            "global_model_reference": "m7-9",
            "l2_calibration": {
                "version": "per-l2-v1",
                "output_label_maps": {"arousal_coarse": {"low": "medium"}},
            },
        },
    )
    assert out["arousal_coarse"] == "medium"
    assert meta["applied"] is True
    assert meta["changed"]["arousal_coarse"] == {"from": "low", "to": "medium"}


def test_l2_skips_on_global_model_mismatch() -> None:
    pred = {"activity": "baseline", "arousal_coarse": "low", "valence_coarse": "neutral"}
    out, meta = apply_adaptation_l2(
        pred,
        {
            "active_personalization_level": "light",
            "global_model_reference": "other",
            "l2_calibration": {
                "global_model_reference_match": "m7-9",
                "output_label_maps": {"arousal_coarse": {"low": "medium"}},
            },
        },
    )
    assert out["arousal_coarse"] == "low"
    assert meta["applied"] is False
    assert meta["reason"] == "global_model_reference_mismatch"


def test_l2_full_same_as_light_for_maps() -> None:
    pred = {"activity": "baseline", "arousal_coarse": "low", "valence_coarse": "unknown"}
    out, meta = apply_adaptation_l2(
        pred,
        {
            "active_personalization_level": "full",
            "l2_calibration": {"output_label_maps": {"arousal_coarse": {"low": "high"}}},
        },
    )
    assert out["arousal_coarse"] == "high"
    assert meta["applied"] is True
