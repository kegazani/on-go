from __future__ import annotations

from live_inference_api.features import extract_watch_features


def test_extract_watch_features_empty() -> None:
    features = extract_watch_features([], [], None, 15.0, 0)
    assert features["meta_segment_duration_sec"] == 15.0
    assert features["meta_source_sample_count"] == 0.0
    assert features["watch_acc_c0__mean"] == 0.0
    assert features["watch_bvp_c0__mean"] == 0.0


def test_extract_watch_features_acc_and_hr() -> None:
    acc = [
        {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0},
        {"acc_x_g": -0.1, "acc_y_g": 0.1, "acc_z_g": 0.9},
    ]
    hr = [
        {"hr_bpm": 72},
        {"hr_bpm": 74},
        {"hr_bpm": 76},
    ]
    features = extract_watch_features(acc, hr, None, 15.0, 5)
    assert features["meta_segment_duration_sec"] == 15.0
    assert features["meta_source_sample_count"] == 5
    assert abs(features["watch_acc_c0__mean"] - 0.0) < 0.001
    assert features["watch_acc_c0__min"] <= features["watch_acc_c0__max"]
    assert 72 <= features["watch_bvp_c0__mean"] <= 76
    assert features["watch_bvp_c0__last"] == 76


def test_extract_watch_features_manifest_layout_includes_rr_and_fusion_proxies() -> None:
    acc = [
        {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0},
        {"acc_x_g": 0.2, "acc_y_g": 0.1, "acc_z_g": 0.9},
    ]
    hr = [{"hr_bpm": 72}, {"hr_bpm": 75}]
    rr = [{"rr_ms": 820}, {"rr_ms": 790}, {"rr_ms": 810}]
    features = extract_watch_features(
        acc,
        hr,
        rr,
        15.0,
        7,
        heart_source="polar_hr",
        manifest_layout=True,
    )
    assert "chest_rr_mean_nn" in features
    assert features["chest_rr_mean_nn"] > 0
    assert "polar_quality_rr_coverage_ratio" in features
    assert "fusion_hr_motion_mean_product" in features


def test_extract_watch_features_manifest_single_rr_populates_chest_rr_block() -> None:
    acc = [{"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}]
    hr = [{"hr_bpm": 72}]
    features = extract_watch_features(
        acc,
        hr,
        [{"rr_ms": 800.0}],
        15.0,
        3,
        heart_source="polar_hr",
        manifest_layout=True,
    )
    assert features["chest_rr_mean_nn"] == 800.0
    assert features["chest_rr_rmssd"] == 0.0
    assert features["polar_quality_rr_valid_count"] == 1.0


def test_extract_watch_features_activity_context_numeric_stats() -> None:
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
        activity_context_samples=[{"confidence": 0.8}, {"confidence": 0.9}],
    )
    assert features["watch_activity_context_confidence__mean"] == 0.85
    assert features["watch_activity_context_confidence__last"] == 0.9


def test_extract_watch_features_manifest_watch_hr_maps_to_chest_ecg_proxy() -> None:
    acc = [{"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}]
    hr = [{"hr_bpm": 68}, {"hr_bpm": 70}]
    features = extract_watch_features(
        acc,
        hr,
        None,
        15.0,
        3,
        heart_source="watch_heart_rate",
        manifest_layout=True,
    )
    assert features.get("watch_bvp_c0__mean") == 69.0
    assert features.get("watch_bvp_c0__last") == 70.0
    assert features.get("chest_ecg_c0__mean") == 69.0
    assert features.get("chest_ecg_c0__last") == 70.0
