from __future__ import annotations

import json

from modeling_baselines.pipeline import (
    GaussianNBClassifier,
    PipelinePaths,
    SegmentExample,
    FullPersonalizationVariantResult,
    H5WeakLabelLabelFreeVariantResult,
    _anti_collapse_diagnostics,
    _build_h5_model_comparison_rows,
    _build_m7_3_polar_first_variants,
    _build_m7_9_polar_expanded_variants,
    _compose_weak_labels,
    _build_h2_model_comparison_rows,
    _build_h3_model_comparison_rows,
    _build_loso_model_comparison_rows,
    _build_extended_model_zoo_variants,
    _loso_fold_examples,
    _arousal_coarse_class,
    _select_feature_names,
    _segment_sort_key,
    _subject_label_mapping,
    LightPersonalizationVariantResult,
    run_m7_4_runtime_candidate_gate,
    run_m7_5_runtime_bundle_export,
    run_m7_9_runtime_bundle_export,
)
from modeling_baselines.main import _build_parser
from modeling_baselines.metrics import compute_classification_metrics
import numpy as np


def test_select_feature_names_drops_protocol_shortcuts_and_keeps_requested_prefixes() -> None:
    all_feature_names = [
        "meta_segment_duration_sec",
        "meta_source_sample_count",
        "watch_acc_c0__mean",
        "watch_bvp_c0__mean",
        "chest_ecg_c0__mean",
    ]
    selected = _select_feature_names(all_feature_names, ("watch_",))
    assert selected == [
        "watch_acc_c0__mean",
        "watch_bvp_c0__mean",
    ]


def test_gaussian_nb_classifier_predicts_expected_labels_on_separable_data() -> None:
    features = np.asarray(
        [
            [0.0, 0.0],
            [0.1, 0.2],
            [3.0, 3.2],
            [3.1, 2.9],
        ],
        dtype=float,
    )
    labels = ["low", "low", "high", "high"]
    model = GaussianNBClassifier()
    model.fit(features, labels)
    predicted = model.predict(np.asarray([[0.05, 0.1], [3.2, 3.0]], dtype=float))
    assert predicted == ["low", "high"]


def test_arousal_coarse_class_mapping() -> None:
    assert _arousal_coarse_class(2) == "low"
    assert _arousal_coarse_class(5) == "medium"
    assert _arousal_coarse_class(8) == "high"


def test_extended_model_zoo_builds_large_variant_set() -> None:
    variants = _build_extended_model_zoo_variants()
    names = {item.variant_name for item in variants}
    assert "watch_only_random_forest" in names
    assert "fusion_random_forest" in names
    assert "fusion_xgboost" in names
    assert "fusion_lightgbm" in names
    assert "fusion_catboost" in names
    assert len(variants) >= 35


def test_polar_first_ablation_matrix_is_explicit_and_ordered() -> None:
    variants = _build_m7_3_polar_first_variants()
    assert [item.variant_name for item in variants] == [
        "polar_only",
        "watch_motion_only",
        "polar+watch_motion",
    ]
    assert variants[0].feature_prefixes == ("chest_ecg_",)
    assert variants[1].feature_prefixes == ("watch_acc_",)
    assert variants[2].feature_prefixes == ("chest_ecg_", "watch_acc_")


def test_anti_collapse_diagnostics_flags_single_class_predictions() -> None:
    diagnostics = _anti_collapse_diagnostics(
        test_target=["low", "medium", "high", "medium"],
        test_predicted=["low", "low", "low", "low"],
    )
    assert diagnostics["status"] == "collapsed"
    assert diagnostics["passed"] is False
    assert diagnostics["predicted_unique_classes"] == 1
    assert diagnostics["dominant_share"] == 1.0


def test_main_parser_exposes_m7_3_polar_first_run_kind() -> None:
    parser = _build_parser()
    run_kind_action = next(action for action in parser._actions if action.dest == "run_kind")
    assert "m7-3-polar-first-training-dataset-build" in run_kind_action.choices
    assert "polar-first-training-dataset-build" in run_kind_action.choices
    assert "m7-5-runtime-bundle-export" in run_kind_action.choices
    assert "m7-9-polar-expanded-fusion-benchmark" in run_kind_action.choices
    assert "m7-9-runtime-bundle-export" in run_kind_action.choices


def test_m7_9_ablation_matrix_is_explicit_and_ordered() -> None:
    variants = _build_m7_9_polar_expanded_variants()
    assert [item.variant_name for item in variants] == [
        "polar_cardio_only",
        "watch_motion_only",
        "polar_expanded_fusion",
    ]
    assert variants[0].feature_prefixes == ("chest_ecg_", "chest_rr_", "polar_quality_")
    assert variants[1].feature_prefixes == ("watch_acc_",)
    assert variants[2].feature_prefixes == (
        "chest_ecg_",
        "chest_rr_",
        "watch_acc_",
        "fusion_hr_motion_",
        "polar_quality_",
    )


def _m79_export_fusion_feature_row() -> dict[str, float]:
    return {
        "chest_ecg_c0__mean": 0.1,
        "chest_ecg_c0__std": 0.02,
        "chest_rr_mean_nn": 800.0,
        "chest_rr_rmssd": 40.0,
        "watch_acc_c0__mean": 0.1,
        "watch_acc_c0__std": 0.05,
        "fusion_hr_motion_mean_product": 0.02,
        "polar_quality_rr_coverage_ratio": 1.0,
    }


def _m79_export_benchmark_report() -> dict[str, object]:
    winner = {
        "variant_name": "polar_expanded_fusion",
        "model_family": "stochastic_gradient_linear_classifier",
        "classifier_kind": "sgd_linear",
        "modality_group": "polar_expanded_fusion",
        "value": 0.5,
        "claim_status": "supported",
        "anti_collapse_status": "ok",
    }
    arousal_watch_only = {
        "variant_name": "watch_motion_only",
        "model_family": "stochastic_gradient_linear_classifier",
        "classifier_kind": "sgd_linear",
        "modality_group": "watch_motion_only",
        "value": 0.55,
        "claim_status": "supported",
        "anti_collapse_status": "ok",
    }
    return {
        "experiment_id": "m7-9-benchmark-test",
        "comparison_summary": {
            "winner_by_track": {
                "activity": dict(winner),
                "arousal_coarse": dict(arousal_watch_only),
                "valence_coarse": dict(winner),
            }
        },
    }


def _m79_export_test_examples() -> list[SegmentExample]:
    base = _m79_export_fusion_feature_row()
    return [
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S1",
            session_id="wesad:S1:session:1",
            segment_id="seg_train_1",
            split="train",
            activity_label="rest",
            arousal_score=2,
            arousal_coarse="low",
            valence_score=2,
            valence_coarse="negative",
            source_label_value="1",
            features=dict(base),
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S2",
            session_id="wesad:S2:session:1",
            segment_id="seg_train_2",
            split="train",
            activity_label="exercise",
            arousal_score=8,
            arousal_coarse="high",
            valence_score=8,
            valence_coarse="positive",
            source_label_value="2",
            features={k: v * 2.0 if k != "polar_quality_rr_coverage_ratio" else v for k, v in base.items()},
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S3",
            session_id="wesad:S3:session:1",
            segment_id="seg_validation_1",
            split="validation",
            activity_label="rest",
            arousal_score=3,
            arousal_coarse="low",
            valence_score=3,
            valence_coarse="negative",
            source_label_value="1",
            features=dict(base),
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S4",
            session_id="wesad:S4:session:1",
            segment_id="seg_test_1",
            split="test",
            activity_label="rest",
            arousal_score=2,
            arousal_coarse="low",
            valence_score=2,
            valence_coarse="negative",
            source_label_value="1",
            features=dict(base),
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S5",
            session_id="wesad:S5:session:1",
            segment_id="seg_test_2",
            split="test",
            activity_label="exercise",
            arousal_score=8,
            arousal_coarse="high",
            valence_score=8,
            valence_coarse="positive",
            source_label_value="2",
            features={k: v * 2.0 if k != "polar_quality_rr_coverage_ratio" else v for k, v in base.items()},
        ),
    ]


def test_m7_9_runtime_bundle_export_arousal_override_uses_fusion_variant(tmp_path, monkeypatch) -> None:
    output_root = tmp_path / "artifacts"
    bench_root = output_root / "wesad" / "wesad-v1" / "m7-9-polar-expanded-fusion-benchmark"
    bench_root.mkdir(parents=True)
    (bench_root / "evaluation-report.json").write_text(
        json.dumps(_m79_export_benchmark_report()),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "modeling_baselines.pipeline._load_examples",
        lambda **kwargs: (_m79_export_test_examples(), {}, {"strategy": "subject-wise"}),
    )
    paths = PipelinePaths(
        segment_labels_path=tmp_path / "segment-labels.jsonl",
        split_manifest_path=tmp_path / "split-manifest.json",
        raw_wesad_root=tmp_path / "raw",
        output_dir=output_root,
    )
    run_m7_9_runtime_bundle_export(
        paths=paths,
        dataset_id="wesad",
        dataset_version="wesad-v1",
        preprocessing_version="e2-v1",
        min_confidence=0.7,
        track_variant_overrides={"arousal_coarse": "polar_expanded_fusion"},
    )
    bundle_root = output_root / "wesad" / "wesad-v1" / "m7-9-runtime-bundle-export"
    manifest = json.loads((bundle_root / "model-bundle.manifest.json").read_text(encoding="utf-8"))
    export_report = json.loads((bundle_root / "runtime-bundle-export-report.json").read_text(encoding="utf-8"))
    assert manifest["bundle_version"] == "v3"
    assert manifest["direct_outputs"]["arousal_coarse"]["modality_group"] == "polar_expanded_fusion"
    assert manifest["direct_outputs"]["arousal_coarse"]["model_path"] == "arousal_coarse_polar_expanded_fusion.joblib"
    assert (bundle_root / "arousal_coarse_polar_expanded_fusion.joblib").exists()
    assert export_report["track_variant_overrides"] == {"arousal_coarse": "polar_expanded_fusion"}
    arousal_winner = next(row for row in export_report["track_winners"] if row["track"] == "arousal_coarse")
    assert arousal_winner["selection"] == "override"
    assert arousal_winner["variant_name"] == "polar_expanded_fusion"


def test_main_parser_exposes_m79_export_override_flags() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "--run-kind",
            "m7-9-runtime-bundle-export",
            "--segment-labels",
            "x.jsonl",
            "--split-manifest",
            "y.json",
            "--wesad-raw-root",
            "z",
            "--output-dir",
            "out",
            "--m79-override-arousal-variant",
            "polar_expanded_fusion",
        ]
    )
    assert args.m79_override_arousal_variant == "polar_expanded_fusion"


def _runtime_bundle_test_examples() -> list[SegmentExample]:
    return [
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S1",
            session_id="wesad:S1:session:1",
            segment_id="seg_train_1",
            split="train",
            activity_label="rest",
            arousal_score=2,
            arousal_coarse="low",
            valence_score=2,
            valence_coarse="negative",
            source_label_value="1",
            features={
                "watch_acc_c0__mean": 0.1,
                "watch_acc_c0__std": 0.05,
                "chest_ecg_c0__mean": 0.1,
            },
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S2",
            session_id="wesad:S2:session:1",
            segment_id="seg_train_2",
            split="train",
            activity_label="exercise",
            arousal_score=8,
            arousal_coarse="high",
            valence_score=8,
            valence_coarse="positive",
            source_label_value="2",
            features={
                "watch_acc_c0__mean": 0.9,
                "watch_acc_c0__std": 0.95,
                "chest_ecg_c0__mean": 0.9,
            },
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S3",
            session_id="wesad:S3:session:1",
            segment_id="seg_validation_1",
            split="validation",
            activity_label="rest",
            arousal_score=3,
            arousal_coarse="low",
            valence_score=3,
            valence_coarse="negative",
            source_label_value="1",
            features={
                "watch_acc_c0__mean": 0.15,
                "watch_acc_c0__std": 0.07,
                "chest_ecg_c0__mean": 0.15,
            },
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S4",
            session_id="wesad:S4:session:1",
            segment_id="seg_test_1",
            split="test",
            activity_label="rest",
            arousal_score=2,
            arousal_coarse="low",
            valence_score=2,
            valence_coarse="negative",
            source_label_value="1",
            features={
                "watch_acc_c0__mean": 0.12,
                "watch_acc_c0__std": 0.04,
                "chest_ecg_c0__mean": 0.08,
            },
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S5",
            session_id="wesad:S5:session:1",
            segment_id="seg_test_2",
            split="test",
            activity_label="exercise",
            arousal_score=8,
            arousal_coarse="high",
            valence_score=8,
            valence_coarse="positive",
            source_label_value="2",
            features={
                "watch_acc_c0__mean": 0.88,
                "watch_acc_c0__std": 0.9,
                "chest_ecg_c0__mean": 0.92,
            },
        ),
    ]


def _runtime_bundle_test_verdict() -> dict[str, object]:
    return {
        "experiment_id": "m7-4-test",
        "source_experiment_id": "m7-3-test",
        "gate_verdict": "pass",
        "gate_passed": True,
        "track_winners": [
            {
                "track": "activity",
                "variant_name": "watch_motion_only",
                "model_family": "stochastic_gradient_linear_classifier",
                "classifier_kind": "sgd_linear",
                "modality_group": "watch_motion_only",
                "value": 0.73,
                "claim_status": "supported",
                "anti_collapse_status": "ok",
            },
            {
                "track": "arousal_coarse",
                "variant_name": "polar+watch_motion",
                "model_family": "stochastic_gradient_linear_classifier",
                "classifier_kind": "sgd_linear",
                "modality_group": "polar_plus_watch_motion",
                "value": 0.58,
                "claim_status": "supported",
                "anti_collapse_status": "ok",
            },
            {
                "track": "valence_coarse",
                "variant_name": "watch_motion_only",
                "model_family": "stochastic_gradient_linear_classifier",
                "classifier_kind": "sgd_linear",
                "modality_group": "watch_motion_only",
                "value": 0.80,
                "claim_status": "supported",
                "anti_collapse_status": "ok",
            },
        ],
    }


def test_m7_5_runtime_bundle_export_fails_fast_when_gate_is_false(tmp_path, monkeypatch) -> None:
    output_root = tmp_path / "artifacts"
    verdict_root = output_root / "wesad" / "wesad-v1" / "m7-4-runtime-candidate-gate"
    verdict_root.mkdir(parents=True, exist_ok=True)
    (verdict_root / "runtime-candidate-verdict.json").write_text(
        json.dumps(
            {
                "gate_verdict": "fail",
                "gate_passed": False,
                "track_winners": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "modeling_baselines.pipeline._load_examples",
        lambda **kwargs: (_runtime_bundle_test_examples(), {}, {"strategy": "subject-wise"}),
    )
    paths = PipelinePaths(
        segment_labels_path=tmp_path / "segment-labels.jsonl",
        split_manifest_path=tmp_path / "split-manifest.json",
        raw_wesad_root=tmp_path / "raw",
        output_dir=output_root,
    )

    try:
        run_m7_5_runtime_bundle_export(
            paths=paths,
            dataset_id="wesad",
            dataset_version="wesad-v1",
            preprocessing_version="e2-v1",
            min_confidence=0.7,
        )
    except RuntimeError as exc:
        assert "gate_passed=true" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected M7.5 export to fail fast when gate_passed=false")


def test_m7_5_runtime_bundle_export_writes_manifest_and_smoke_summary(tmp_path, monkeypatch) -> None:
    output_root = tmp_path / "artifacts"
    verdict_root = output_root / "wesad" / "wesad-v1" / "m7-4-runtime-candidate-gate"
    verdict_root.mkdir(parents=True, exist_ok=True)
    (verdict_root / "runtime-candidate-verdict.json").write_text(
        json.dumps(_runtime_bundle_test_verdict()),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "modeling_baselines.pipeline._load_examples",
        lambda **kwargs: (_runtime_bundle_test_examples(), {}, {"strategy": "subject-wise"}),
    )
    paths = PipelinePaths(
        segment_labels_path=tmp_path / "segment-labels.jsonl",
        split_manifest_path=tmp_path / "split-manifest.json",
        raw_wesad_root=tmp_path / "raw",
        output_dir=output_root,
    )

    result = run_m7_5_runtime_bundle_export(
        paths=paths,
        dataset_id="wesad",
        dataset_version="wesad-v1",
        preprocessing_version="e2-v1",
        min_confidence=0.7,
    )

    bundle_root = output_root / "wesad" / "wesad-v1" / "m7-5-runtime-bundle-export"
    manifest = json.loads((bundle_root / "model-bundle.manifest.json").read_text(encoding="utf-8"))
    export_report = json.loads((bundle_root / "runtime-bundle-export-report.json").read_text(encoding="utf-8"))
    smoke_summary = json.loads((bundle_root / "runtime-bundle-smoke-summary.json").read_text(encoding="utf-8"))

    assert result["bundle_id"] == "on-go-m7-5-runtime-bundle-export"
    assert result["gate_passed"] is True
    assert manifest["bundle_id"] == "on-go-m7-5-runtime-bundle-export"
    assert set(manifest["direct_outputs"].keys()) == {"activity", "arousal_coarse", "valence_coarse"}
    assert manifest["direct_outputs"]["activity"]["model_path"].endswith(".joblib")
    assert manifest["direct_outputs"]["activity"]["feature_names_path"] == "activity_feature_names.json"
    assert (bundle_root / "activity_feature_names.json").exists()
    assert (bundle_root / "arousal_coarse_feature_names.json").exists()
    assert (bundle_root / "valence_coarse_feature_names.json").exists()
    assert (bundle_root / "activity_watch_motion_only.joblib").exists()
    assert (bundle_root / "arousal_coarse_polar_plus_watch_motion.joblib").exists()
    assert (bundle_root / "valence_coarse_watch_motion_only.joblib").exists()
    assert export_report["track_winners"][0]["track"] == "activity"
    assert smoke_summary["passed"] is True
    assert smoke_summary["track_count"] == 3
    assert all(item["feature_count"] > 0 for item in smoke_summary["track_summaries"])



def test_subject_label_mapping_picks_majority_true_label_per_predicted_bucket() -> None:
    mapping = _subject_label_mapping(
        predicted=["a", "a", "b", "b", "b"],
        truth=["x", "x", "y", "y", "z"],
    )
    assert mapping == {"a": "x", "b": "y"}


def test_segment_sort_key_prefers_numeric_segment_order() -> None:
    rows = [
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S2",
            session_id="wesad:S2:session:1",
            segment_id="seg_10",
            split="test",
            activity_label="baseline_rest",
            arousal_score=3,
            arousal_coarse="low",
            valence_score=5,
            valence_coarse="neutral",
            source_label_value="1",
            features={"meta_segment_duration_sec": 1.0, "meta_source_sample_count": 2.0},
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S2",
            session_id="wesad:S2:session:1",
            segment_id="seg_2",
            split="test",
            activity_label="baseline_rest",
            arousal_score=3,
            arousal_coarse="low",
            valence_score=5,
            valence_coarse="neutral",
            source_label_value="1",
            features={"meta_segment_duration_sec": 1.0, "meta_source_sample_count": 2.0},
        ),
    ]
    sorted_rows = sorted(rows, key=_segment_sort_key)
    assert [item.segment_id for item in sorted_rows] == ["seg_2", "seg_10"]


def test_loso_fold_examples_assigns_train_validation_test_by_subject() -> None:
    base_rows = [
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S2",
            session_id="wesad:S2:session:1",
            segment_id="seg_1",
            split="train",
            activity_label="seated_rest",
            arousal_score=2,
            arousal_coarse="low",
            valence_score=5,
            valence_coarse="neutral",
            source_label_value="1",
            features={"watch_acc_c0__mean": 0.1},
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S3",
            session_id="wesad:S3:session:1",
            segment_id="seg_2",
            split="train",
            activity_label="focused_cognitive_task",
            arousal_score=8,
            arousal_coarse="high",
            valence_score=5,
            valence_coarse="neutral",
            source_label_value="2",
            features={"watch_acc_c0__mean": 0.2},
        ),
        SegmentExample(
            dataset_id="wesad",
            dataset_version="wesad-v1",
            subject_id="wesad:S4",
            session_id="wesad:S4:session:1",
            segment_id="seg_3",
            split="train",
            activity_label="recovery_rest",
            arousal_score=2,
            arousal_coarse="low",
            valence_score=5,
            valence_coarse="neutral",
            source_label_value="4",
            features={"watch_acc_c0__mean": 0.3},
        ),
    ]
    fold_rows = _loso_fold_examples(
        examples=base_rows,
        test_subject_id="wesad:S4",
        validation_subject_id="wesad:S3",
    )
    split_by_subject = {row.subject_id: row.split for row in fold_rows}
    assert split_by_subject == {"wesad:S2": "train", "wesad:S3": "validation", "wesad:S4": "test"}


def test_build_loso_model_comparison_rows_aggregates_mean_std_and_delta() -> None:
    variant_fold_scores = {
        ("watch_only_centroid", "activity"): [(1, 0.6), (2, 0.7), (3, 0.8)],
        ("watch_only_ada_boost", "activity"): [(1, 0.8), (2, 0.8), (3, 0.8)],
        ("watch_only_centroid", "arousal_coarse"): [(1, 0.5), (2, 0.6), (3, 0.7)],
        ("watch_only_ada_boost", "arousal_coarse"): [(1, 0.55), (2, 0.65), (3, 0.75)],
    }
    variant_meta = {
        "watch_only_centroid": {
            "model_family": "nearest_centroid_feature_baseline",
            "classifier_kind": "centroid",
            "modality_group": "watch_only",
            "feature_count": 37,
        },
        "watch_only_ada_boost": {
            "model_family": "adaboost",
            "classifier_kind": "ada_boost",
            "modality_group": "watch_only",
            "feature_count": 37,
        },
    }
    rows = _build_loso_model_comparison_rows(
        variant_fold_scores=variant_fold_scores,
        variant_meta=variant_meta,
        expected_fold_count=3,
        baseline_variant_name="watch_only_centroid",
    )
    target = next(row for row in rows if row["variant_name"] == "watch_only_ada_boost" and row["track"] == "activity")
    assert target["evaluation_mode"] == "loso"
    assert target["mean_macro_f1"] == 0.8
    assert target["delta_vs_watch_only"] == 0.1


def test_h2_model_comparison_rows_include_global_and_personalized() -> None:
    result = LightPersonalizationVariantResult(
        variant_name="watch_only_ada_boost",
        model_family="adaboost",
        classifier_kind="ada_boost",
        modality_group="watch_only",
        input_modalities=["watch_acc"],
        feature_names=["watch_acc_c0__mean"],
        calibration_segments=2,
        global_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "a"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["low", "low"]),
        },
        personalized_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "b"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["low", "high"]),
        },
        per_subject_rows=[
            {
                "variant_name": "watch_only_ada_boost",
                "track": "activity",
                "subject_id": "wesad:S2",
                "global_macro_f1": 0.5,
                "personalized_macro_f1": 1.0,
                "gain_macro_f1": 0.5,
                "global_balanced_accuracy": 0.5,
                "personalized_balanced_accuracy": 1.0,
                "support": 2,
                "calibration_segments": 2,
            },
            {
                "variant_name": "watch_only_ada_boost",
                "track": "arousal_coarse",
                "subject_id": "wesad:S2",
                "global_macro_f1": 0.5,
                "personalized_macro_f1": 1.0,
                "gain_macro_f1": 0.5,
                "global_balanced_accuracy": 0.5,
                "personalized_balanced_accuracy": 1.0,
                "support": 2,
                "calibration_segments": 2,
            },
        ],
        prediction_rows=[],
        budget_rows=[],
        split_summary={},
    )
    rows = _build_h2_model_comparison_rows([result])
    assert len(rows) == 4
    personalized_activity = next(
        row for row in rows if row["track"] == "activity" and row["evaluation_mode"] == "personalized"
    )
    assert float(personalized_activity["delta_vs_global"]) > 0.0


def test_h3_model_comparison_rows_include_full_mode_and_delta_vs_light() -> None:
    result = FullPersonalizationVariantResult(
        variant_name="fusion_catboost",
        model_family="catboost_multiclass",
        classifier_kind="catboost",
        modality_group="fusion",
        input_modalities=["watch_acc", "chest_ecg"],
        feature_names=["watch_acc_c0__mean", "chest_ecg_c0__mean"],
        calibration_segments=2,
        adaptation_weight=5,
        global_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "a"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["low", "low"]),
        },
        light_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "b"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["low", "high"]),
        },
        full_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "b"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["low", "high"]),
        },
        per_subject_rows=[
            {
                "variant_name": "fusion_catboost",
                "track": "activity",
                "subject_id": "wesad:S2",
                "global_macro_f1": 0.5,
                "light_macro_f1": 1.0,
                "full_macro_f1": 1.0,
                "gain_light_vs_global": 0.5,
                "gain_full_vs_global": 0.5,
                "gain_full_vs_light": 0.0,
                "support": 2,
                "calibration_segments": 2,
            },
            {
                "variant_name": "fusion_catboost",
                "track": "arousal_coarse",
                "subject_id": "wesad:S2",
                "global_macro_f1": 0.5,
                "light_macro_f1": 1.0,
                "full_macro_f1": 1.0,
                "gain_light_vs_global": 0.5,
                "gain_full_vs_global": 0.5,
                "gain_full_vs_light": 0.0,
                "support": 2,
                "calibration_segments": 2,
            },
        ],
        prediction_rows=[],
        budget_rows=[],
        split_summary={},
    )
    rows = _build_h3_model_comparison_rows([result])
    assert len(rows) == 6
    full_activity = next(
        row for row in rows if row["track"] == "activity" and row["evaluation_mode"] == "full"
    )
    assert float(full_activity["delta_vs_global"]) >= 0.0
    assert "delta_vs_light" in full_activity


def test_compose_weak_labels_keeps_every_second_true_label() -> None:
    weak = _compose_weak_labels(
        truth=["a", "b", "c", "d"],
        pseudo=["x", "y", "z", "w"],
    )
    assert weak == ["a", "y", "c", "w"]


def test_h5_model_comparison_rows_include_label_free_mode() -> None:
    result = H5WeakLabelLabelFreeVariantResult(
        variant_name="fusion_catboost",
        model_family="catboost_multiclass",
        classifier_kind="catboost",
        modality_group="fusion",
        input_modalities=["watch_acc", "chest_ecg"],
        feature_names=["watch_acc_c0__mean", "chest_ecg_c0__mean"],
        calibration_segments=2,
        adaptation_weight=5,
        global_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "a"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["low", "low"]),
        },
        weak_label_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "b"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["low", "high"]),
        },
        label_free_metrics={
            "activity": compute_classification_metrics(["a", "b"], ["a", "b"]),
            "arousal_coarse": compute_classification_metrics(["low", "high"], ["high", "high"]),
        },
        per_subject_rows=[
            {
                "variant_name": "fusion_catboost",
                "track": "activity",
                "subject_id": "wesad:S2",
                "global_macro_f1": 0.5,
                "weak_label_macro_f1": 1.0,
                "label_free_macro_f1": 1.0,
                "gain_weak_label_vs_global": 0.5,
                "gain_label_free_vs_global": 0.5,
                "gain_label_free_vs_weak_label": 0.0,
                "support": 2,
                "calibration_segments": 2,
            },
            {
                "variant_name": "fusion_catboost",
                "track": "arousal_coarse",
                "subject_id": "wesad:S2",
                "global_macro_f1": 0.5,
                "weak_label_macro_f1": 1.0,
                "label_free_macro_f1": 0.333333,
                "gain_weak_label_vs_global": 0.5,
                "gain_label_free_vs_global": -0.166667,
                "gain_label_free_vs_weak_label": -0.666667,
                "support": 2,
                "calibration_segments": 2,
            },
        ],
        prediction_rows=[],
        budget_rows=[],
        split_summary={},
    )
    rows = _build_h5_model_comparison_rows([result])
    assert len(rows) == 6
    label_free_activity = next(
        row for row in rows if row["track"] == "activity" and row["evaluation_mode"] == "label_free"
    )
    assert "delta_vs_weak_label" in label_free_activity


def test_m7_4_runtime_candidate_gate_fails_when_anti_collapse_flagged(tmp_path) -> None:
    output_root = tmp_path / "artifacts"
    m7_3_root = output_root / "wesad" / "wesad-v1" / "m7-3-polar-first-training-dataset-build"
    m7_3_root.mkdir(parents=True, exist_ok=True)
    (m7_3_root / "evaluation-report.json").write_text(
        json.dumps(
            {
                "experiment_id": "m7-3-test",
                "comparison_summary": {
                    "winner_by_track": {
                        "activity": {
                            "variant_name": "watch_motion_only",
                            "model_family": "ridge_classifier_linear",
                            "classifier_kind": "ridge_classifier",
                            "modality_group": "watch_motion_only",
                            "value": 0.6,
                            "claim_status": "supported",
                            "anti_collapse_status": "ok",
                        },
                        "arousal_coarse": {
                            "variant_name": "watch_motion_only",
                            "model_family": "ridge_classifier_linear",
                            "classifier_kind": "ridge_classifier",
                            "modality_group": "watch_motion_only",
                            "value": 0.5,
                            "claim_status": "supported",
                            "anti_collapse_status": "ok",
                        },
                        "valence_coarse": {
                            "variant_name": "watch_motion_only",
                            "model_family": "ridge_classifier_linear",
                            "classifier_kind": "ridge_classifier",
                            "modality_group": "watch_motion_only",
                            "value": 0.7,
                            "claim_status": "supported",
                            "anti_collapse_status": "ok",
                        },
                    }
                },
                "anti_collapse_summary": {
                    "passed": False,
                    "threshold": 0.9,
                    "flagged_rows": [
                        {"variant_name": "polar_only", "track": "activity", "status": "near_constant", "dominant_share": 0.93}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    paths = PipelinePaths(
        segment_labels_path=tmp_path / "segment-labels.jsonl",
        split_manifest_path=tmp_path / "split-manifest.json",
        raw_wesad_root=tmp_path / "raw",
        output_dir=output_root,
    )
    result = run_m7_4_runtime_candidate_gate(
        paths=paths,
        dataset_id="wesad",
        dataset_version="wesad-v1",
        preprocessing_version="e2-v1",
        min_confidence=0.7,
    )
    assert result["gate_passed"] is False
    assert result["gate_verdict"] == "fail"
    verdict = json.loads(
        (output_root / "wesad" / "wesad-v1" / "m7-4-runtime-candidate-gate" / "runtime-candidate-verdict.json").read_text(
            encoding="utf-8"
        )
    )
    assert "anti_collapse_summary_failed" in verdict["global_issues"]
    assert "flagged_rows_present" in verdict["global_issues"]
    assert verdict["track_failures"] == []
    assert verdict["remediation_actions"][0] == {
        "action": "retrain_or_rebalance_flagged_tracks",
        "reason": "anti-collapse gate failed on at least one variant/track",
        "blocked_step": "P5 Runtime Bundle Export",
    }
    assert verdict["remediation_actions"][1] == {
        "action": "targeted_remediation_for_variant_track",
        "variant_name": "polar_only",
        "track": "activity",
        "issue": "near_constant",
        "dominant_share": 0.93,
    }


def test_m7_4_runtime_candidate_gate_passes_when_all_winners_supported(tmp_path) -> None:
    output_root = tmp_path / "artifacts"
    m7_3_root = output_root / "wesad" / "wesad-v1" / "m7-3-polar-first-training-dataset-build"
    m7_3_root.mkdir(parents=True, exist_ok=True)
    (m7_3_root / "evaluation-report.json").write_text(
        json.dumps(
            {
                "experiment_id": "m7-3-test-ok",
                "comparison_summary": {
                    "winner_by_track": {
                        "activity": {"variant_name": "fusion", "value": 0.7, "claim_status": "supported", "anti_collapse_status": "ok"},
                        "arousal_coarse": {"variant_name": "fusion", "value": 0.6, "claim_status": "supported", "anti_collapse_status": "ok"},
                        "valence_coarse": {"variant_name": "fusion", "value": 0.8, "claim_status": "supported", "anti_collapse_status": "ok"},
                    }
                },
                "anti_collapse_summary": {"passed": True, "threshold": 0.9, "flagged_rows": []},
            }
        ),
        encoding="utf-8",
    )
    paths = PipelinePaths(
        segment_labels_path=tmp_path / "segment-labels.jsonl",
        split_manifest_path=tmp_path / "split-manifest.json",
        raw_wesad_root=tmp_path / "raw",
        output_dir=output_root,
    )
    result = run_m7_4_runtime_candidate_gate(
        paths=paths,
        dataset_id="wesad",
        dataset_version="wesad-v1",
        preprocessing_version="e2-v1",
        min_confidence=0.7,
    )
    assert result["gate_passed"] is True
    assert result["gate_verdict"] == "pass"
    verdict = json.loads(
        (output_root / "wesad" / "wesad-v1" / "m7-4-runtime-candidate-gate" / "runtime-candidate-verdict.json").read_text(
            encoding="utf-8"
        )
    )
    assert verdict["track_failures"] == []
    assert verdict["global_issues"] == []
    assert verdict["remediation_actions"] == []
    assert verdict["anti_collapse_summary"]["flagged_rows"] == []
    assert verdict["next_step_if_pass"] == "P5 Runtime Bundle Export"
    assert verdict["next_step_if_fail"] == "P4 remediation loop"
    assert all(row["claim_status"] == "supported" for row in verdict["track_winners"])
    assert all(row["anti_collapse_status"] == "ok" for row in verdict["track_winners"])


def test_m7_4_runtime_candidate_gate_blocks_missing_and_unsupported_winners(tmp_path) -> None:
    output_root = tmp_path / "artifacts"
    m7_3_root = output_root / "wesad" / "wesad-v1" / "m7-3-polar-first-training-dataset-build"
    m7_3_root.mkdir(parents=True, exist_ok=True)
    (m7_3_root / "evaluation-report.json").write_text(
        json.dumps(
            {
                "experiment_id": "m7-3-guardrail-test",
                "comparison_summary": {
                    "winner_by_track": {
                        "activity": {
                            "variant_name": "polar_only",
                            "model_family": "ridge_classifier_linear",
                            "classifier_kind": "ridge_classifier",
                            "modality_group": "polar_only",
                            "value": 0.6,
                            "claim_status": "supported",
                            "anti_collapse_status": "ok",
                        },
                        "arousal_coarse": {
                            "variant_name": None,
                            "model_family": None,
                            "classifier_kind": None,
                            "modality_group": None,
                            "value": None,
                            "claim_status": "supported",
                            "anti_collapse_status": "ok",
                        },
                        "valence_coarse": {
                            "variant_name": "polar_plus_watch",
                            "model_family": "ridge_classifier_linear",
                            "classifier_kind": "ridge_classifier",
                            "modality_group": "polar_plus_watch",
                            "value": 0.68,
                            "claim_status": "inconclusive_positive",
                            "anti_collapse_status": "ok",
                        },
                    }
                },
                "anti_collapse_summary": {
                    "passed": True,
                    "threshold": 0.9,
                    "flagged_rows": [],
                },
            }
        ),
        encoding="utf-8",
    )
    paths = PipelinePaths(
        segment_labels_path=tmp_path / "segment-labels.jsonl",
        split_manifest_path=tmp_path / "split-manifest.json",
        raw_wesad_root=tmp_path / "raw",
        output_dir=output_root,
    )
    result = run_m7_4_runtime_candidate_gate(
        paths=paths,
        dataset_id="wesad",
        dataset_version="wesad-v1",
        preprocessing_version="e2-v1",
        min_confidence=0.7,
    )
    assert result["gate_passed"] is False
    assert result["gate_verdict"] == "fail"
    verdict = json.loads(
        (output_root / "wesad" / "wesad-v1" / "m7-4-runtime-candidate-gate" / "runtime-candidate-verdict.json").read_text(
            encoding="utf-8"
        )
    )
    assert verdict["global_issues"] == []
    assert {item["track"]: item["issues"] for item in verdict["track_failures"]} == {
        "arousal_coarse": ["missing_winner"],
        "valence_coarse": ["claim_not_supported"],
    }
    assert verdict["remediation_actions"] == [
        {
            "action": "retrain_or_rebalance_flagged_tracks",
            "reason": "anti-collapse gate failed on at least one variant/track",
            "blocked_step": "P5 Runtime Bundle Export",
        }
    ]
