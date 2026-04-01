from __future__ import annotations

from live_inference_api.activity_context_adjust import adjust_activity_label_for_context


def test_adjust_empty_context_unchanged() -> None:
    assert adjust_activity_label_for_context("seated_rest", None) == "seated_rest"
    assert adjust_activity_label_for_context("seated_rest", []) == "seated_rest"


def test_adjust_insufficient_labeled_unchanged() -> None:
    ctx = [{"activity_type": "high_motion", "confidence": 0.9}]
    assert adjust_activity_label_for_context("seated_rest", ctx) == "seated_rest"


def test_adjust_only_numeric_context_unchanged() -> None:
    ctx = [{"confidence": 0.8}, {"confidence": 0.9}]
    assert adjust_activity_label_for_context("seated_rest", ctx) == "seated_rest"


def test_adjust_high_motion_mode_to_light_exercise() -> None:
    ctx = [
        {"activity_type": "high_motion"},
        {"activity_type": "high_motion"},
    ]
    assert adjust_activity_label_for_context("seated_rest", ctx) == "light_exercise"


def test_adjust_light_motion_mode_to_walking() -> None:
    ctx = [
        {"activity_type": "light_motion"},
        {"activity_type": "light_motion"},
    ]
    assert adjust_activity_label_for_context("standing_rest", ctx) == "walking"


def test_adjust_non_rest_ml_unchanged() -> None:
    ctx = [{"activity_type": "high_motion"}, {"activity_type": "high_motion"}]
    assert adjust_activity_label_for_context("walking", ctx) == "walking"


def test_adjust_rest_mode_high_motion_fraction() -> None:
    ctx = [{"activity_type": "rest"}] * 6 + [{"activity_type": "light_motion"}] * 4
    assert adjust_activity_label_for_context("seated_rest", ctx) == "walking"


def test_adjust_activity_type_camel_case() -> None:
    ctx = [{"activityType": "light_motion"}, {"activityType": "light_motion"}]
    assert adjust_activity_label_for_context("seated_rest", ctx) == "walking"


def test_extract_watch_features_motion_level_stats() -> None:
    from live_inference_api.features import extract_watch_features

    acc = [{"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}]
    hr = [{"hr_bpm": 72}]
    features = extract_watch_features(
        acc,
        hr,
        None,
        15.0,
        3,
        heart_source="polar_hr",
        manifest_layout=True,
        activity_context_samples=[
            {"activity_type": "rest"},
            {"activity_type": "high_motion"},
        ],
    )
    assert features["watch_activity_context_motion_level__mean"] == 1.0
    assert features["watch_activity_context_motion_level__max"] == 2.0
    assert features["watch_activity_context_motion_level__min"] == 0.0
