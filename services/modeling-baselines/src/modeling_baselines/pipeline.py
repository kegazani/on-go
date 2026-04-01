from __future__ import annotations

import csv
import json
import math
import pickle
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

import numpy as np

from modeling_baselines.estimators import (
    build_estimator_classifier,
    get_classifier_config,
    supported_classifier_kinds,
)
from modeling_baselines.metrics import (
    ClassificationMetrics,
    compute_classification_metrics,
    compute_mae,
    compute_quadratic_weighted_kappa,
    compute_spearman_rho,
)

LABEL_RATE_HZ = 700.0
WATCH_MODALITY_RATES_HZ: dict[str, float] = {
    "ACC": 32.0,
    "BVP": 64.0,
    "EDA": 4.0,
    "TEMP": 4.0,
}
CHEST_MODALITY_RATES_HZ: dict[str, float] = {
    "ACC": 700.0,
    "ECG": 700.0,
    "EDA": 700.0,
    "EMG": 700.0,
    "Resp": 700.0,
    "Temp": 700.0,
}
# WESAD segment boundaries are protocol-defined. Duration/sample-count metadata can
# encode the scenario itself and dominate the classifier without learning signal patterns.
PROTOCOL_SHORTCUT_FEATURE_NAMES = {
    "meta_segment_duration_sec",
    "meta_source_sample_count",
}
M7_9_CHEST_RR_FEATURE_NAMES = (
    "chest_rr_mean_nn",
    "chest_rr_median_nn",
    "chest_rr_min_nn",
    "chest_rr_max_nn",
    "chest_rr_sdnn",
    "chest_rr_rmssd",
    "chest_rr_sdsd",
    "chest_rr_nn50",
    "chest_rr_pnn50",
    "chest_rr_iqr_nn",
    "chest_rr_mad_nn",
    "chest_rr_cvnn",
    "chest_rr_cvsd",
    "chest_rr_hr_mean",
    "chest_rr_hr_std",
    "chest_rr_hr_min",
    "chest_rr_hr_max",
)
M7_9_POLAR_QUALITY_FEATURE_NAMES = (
    "polar_quality_rr_coverage_ratio",
    "polar_quality_rr_valid_count",
    "polar_quality_rr_outlier_ratio",
)
M7_9_FUSION_FEATURE_NAMES = (
    "fusion_hr_motion_mean_product",
    "fusion_hr_motion_std_product",
    "fusion_hr_motion_mean_ratio",
    "fusion_hr_motion_std_ratio",
    "fusion_hr_motion_mean_delta",
    "fusion_hr_motion_std_delta",
    "fusion_hr_motion_energy_proxy",
    "fusion_hr_motion_stability_proxy",
)


@dataclass(frozen=True)
class SegmentExample:
    dataset_id: str
    dataset_version: str
    subject_id: str
    session_id: str
    segment_id: str
    split: str
    activity_label: str
    arousal_score: int
    arousal_coarse: str
    valence_score: int
    valence_coarse: str
    source_label_value: str
    features: dict[str, float]


@dataclass(frozen=True)
class PipelinePaths:
    segment_labels_path: Path
    split_manifest_path: Path
    raw_wesad_root: Path
    output_dir: Path


@dataclass(frozen=True)
class VariantSpec:
    variant_name: str
    model_family: str
    classifier_kind: str
    feature_prefixes: tuple[str, ...]
    input_modalities: tuple[str, ...]
    description: str
    modality_group: str = "custom"
    hyperparameters: dict[str, Any] | None = None


@dataclass
class VariantRunResult:
    variant_name: str
    model_family: str
    classifier_kind: str
    modality_group: str
    input_modalities: list[str]
    feature_names: list[str]
    activity_validation_pred: list[str]
    activity_test_pred: list[str]
    arousal_validation_pred: list[str]
    arousal_test_pred: list[str]
    arousal_test_score_pred: list[int]
    tracks: dict[str, Any]
    splits: dict[str, Any]
    per_subject_rows: list[dict[str, Any]]
    feature_importance_rows: list[dict[str, Any]]


@dataclass(frozen=True)
class FailedVariantRun:
    variant_name: str
    model_family: str
    classifier_kind: str
    modality_group: str
    input_modalities: list[str]
    error_type: str
    error_message: str


@dataclass
class LightPersonalizationVariantResult:
    variant_name: str
    model_family: str
    classifier_kind: str
    modality_group: str
    input_modalities: list[str]
    feature_names: list[str]
    calibration_segments: int
    global_metrics: dict[str, ClassificationMetrics]
    personalized_metrics: dict[str, ClassificationMetrics]
    per_subject_rows: list[dict[str, Any]]
    prediction_rows: list[dict[str, Any]]
    budget_rows: list[dict[str, Any]]
    split_summary: dict[str, Any]


@dataclass
class FullPersonalizationVariantResult:
    variant_name: str
    model_family: str
    classifier_kind: str
    modality_group: str
    input_modalities: list[str]
    feature_names: list[str]
    calibration_segments: int
    adaptation_weight: int
    global_metrics: dict[str, ClassificationMetrics]
    light_metrics: dict[str, ClassificationMetrics]
    full_metrics: dict[str, ClassificationMetrics]
    per_subject_rows: list[dict[str, Any]]
    prediction_rows: list[dict[str, Any]]
    budget_rows: list[dict[str, Any]]
    split_summary: dict[str, Any]


@dataclass
class H5WeakLabelLabelFreeVariantResult:
    variant_name: str
    model_family: str
    classifier_kind: str
    modality_group: str
    input_modalities: list[str]
    feature_names: list[str]
    calibration_segments: int
    adaptation_weight: int
    global_metrics: dict[str, ClassificationMetrics]
    weak_label_metrics: dict[str, ClassificationMetrics]
    label_free_metrics: dict[str, ClassificationMetrics]
    per_subject_rows: list[dict[str, Any]]
    prediction_rows: list[dict[str, Any]]
    budget_rows: list[dict[str, Any]]
    split_summary: dict[str, Any]


@dataclass
class PolarFirstVariantResult:
    variant_name: str
    model_family: str
    classifier_kind: str
    modality_group: str
    input_modalities: list[str]
    feature_names: list[str]
    activity_test_pred: list[str]
    arousal_test_pred: list[str]
    valence_test_pred: list[str]
    arousal_test_score_pred: list[int]
    valence_test_score_pred: list[int]
    tracks: dict[str, Any]
    splits: dict[str, Any]
    per_subject_rows: list[dict[str, Any]]
    prediction_rows: list[dict[str, Any]]


def run_watch_only_wesad_baseline(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
    model_save_dir: Path | None = None,
) -> dict[str, Any]:
    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variant = VariantSpec(
        variant_name="watch_only_centroid",
        model_family="nearest_centroid_feature_baseline",
        classifier_kind="centroid",
        feature_prefixes=("watch_",),
        input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
        description="Nearest-centroid baseline on wrist-only segment features.",
    )
    variant_result = _evaluate_variant(
        examples=examples,
        variant=variant,
        model_save_dir=model_save_dir,
    )
    timestamp = datetime.now(timezone.utc)
    experiment_id = f"g1-watch-only-wesad-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"

    report = {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "model_family": variant.model_family,
        "input_modalities": list(variant.input_modalities),
        "tracks": variant_result.tracks,
        "splits": variant_result.splits,
        "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        "feature_count": len(variant_result.feature_names),
        "generated_at_utc": timestamp.isoformat(),
    }

    output_root = paths.output_dir / dataset_id / dataset_version / "watch-only-baseline"
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_predictions_csv(
        path=predictions_path,
        rows=_prediction_rows(
            variant_name=variant.variant_name,
            model_family=variant.model_family,
            examples=[item for item in examples if item.split == "test"],
            activity_pred=variant_result.activity_test_pred,
            arousal_pred=variant_result.arousal_test_pred,
            arousal_score_pred=variant_result.arousal_test_score_pred,
        ),
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "examples_total": len(examples),
        "train_examples": variant_result.splits["train"]["segments"],
        "validation_examples": variant_result.splits["validation"]["segments"],
        "test_examples": variant_result.splits["test"]["segments"],
    }


def run_fusion_wesad_comparison(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = [
        VariantSpec(
            variant_name="watch_only_centroid",
            model_family="nearest_centroid_feature_baseline",
            classifier_kind="centroid",
            feature_prefixes=("watch_",),
            input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
            description="Nearest-centroid baseline on wrist-only segment features.",
        ),
        VariantSpec(
            variant_name="chest_only_centroid",
            model_family="nearest_centroid_feature_baseline",
            classifier_kind="centroid",
            feature_prefixes=("chest_",),
            input_modalities=("chest_acc", "chest_ecg", "chest_eda", "chest_emg", "chest_resp", "chest_temp"),
            description="Nearest-centroid baseline on chest-only segment features.",
        ),
        VariantSpec(
            variant_name="fusion_centroid",
            model_family="nearest_centroid_feature_baseline",
            classifier_kind="centroid",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Nearest-centroid fusion baseline on wrist + chest segment features.",
        ),
        VariantSpec(
            variant_name="fusion_gaussian_nb",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Gaussian naive Bayes fusion baseline on wrist + chest segment features.",
        ),
    ]
    variant_results = [_evaluate_variant(examples=examples, variant=item) for item in variants]
    timestamp = datetime.now(timezone.utc)
    experiment_id = f"g2-fusion-wesad-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"

    output_root = paths.output_dir / dataset_id / dataset_version / "fusion-baseline"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    test_examples = [item for item in examples if item.split == "test"]
    comparison_rows = _build_model_comparison_rows(variant_results=variant_results, test_examples=test_examples)
    report = _build_fusion_report(
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        preprocessing_version=preprocessing_version,
        split_manifest=split_manifest,
        labels=labels,
        min_confidence=min_confidence,
        variants=variants,
        variant_results=variant_results,
        comparison_rows=comparison_rows,
        generated_at=timestamp,
    )

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prediction_rows: list[dict[str, Any]] = []
    for variant, result in zip(variants, variant_results):
        test_examples = [item for item in examples if item.split == "test"]
        prediction_rows.extend(
            _prediction_rows(
                variant_name=variant.variant_name,
                model_family=variant.model_family,
                examples=test_examples,
                activity_pred=result.activity_test_pred,
                arousal_pred=result.arousal_test_pred,
                arousal_score_pred=result.arousal_test_score_pred,
            )
        )
    predictions_path = output_root / "predictions-test.csv"
    _write_predictions_csv(path=predictions_path, rows=prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_per_subject_metrics_csv(
        path=per_subject_path,
        rows=[row for result in variant_results for row in result.per_subject_rows],
    )

    comparison_path = output_root / "model-comparison.csv"
    _write_model_comparison_csv(path=comparison_path, rows=comparison_rows)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_research_report_markdown(
            report=report,
            variants=variants,
            variant_results=variant_results,
        ),
        encoding="utf-8",
    )

    _generate_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        variant_results=variant_results,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "examples_total": len(examples),
        "variant_count": len(variants),
    }


def run_e2_3_wesad_polar_watch_benchmark(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = [
        VariantSpec(
            variant_name="polar_rr_only",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("chest_ecg_",),
            input_modalities=("polar_rr_proxy(chest_ecg)",),
            description="Polar RR-only proxy baseline on ECG-derived segment features.",
            modality_group="polar_rr_only",
        ),
        VariantSpec(
            variant_name="polar_rr_acc",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("chest_ecg_", "chest_acc_"),
            input_modalities=("polar_rr_proxy(chest_ecg)", "polar_acc_proxy(chest_acc)"),
            description="Polar RR + ACC proxy baseline on chest ECG/ACC segment features.",
            modality_group="polar_rr_acc",
        ),
        VariantSpec(
            variant_name="watch_plus_polar_fusion",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("watch_", "chest_ecg_", "chest_acc_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "polar_rr_proxy(chest_ecg)",
                "polar_acc_proxy(chest_acc)",
            ),
            description="Fusion of watch context with Polar RR/ACC proxy channels.",
            modality_group="fusion",
        ),
    ]

    variant_results = [_evaluate_variant_for_e2_3(examples=examples, variant=item) for item in variants]
    timestamp = datetime.now(timezone.utc)
    experiment_id = f"e2-3-polar-watch-benchmark-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"

    output_root = paths.output_dir / dataset_id / dataset_version / "e2-3-polar-watch-benchmark"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    test_examples = [item for item in examples if item.split == "test"]
    comparison_rows = _build_e2_3_model_comparison_rows(
        variant_results=variant_results,
        test_examples=test_examples,
        baseline_variant_name="polar_rr_only",
    )
    per_subject_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    for result in variant_results:
        per_subject_rows.extend(result["per_subject_rows"])
        prediction_rows.extend(result["prediction_rows"])

    winner_arousal = max(
        [row for row in comparison_rows if row["track"] == "arousal_coarse"],
        key=lambda item: float(item["value"]),
    )
    winner_valence = max(
        [row for row in comparison_rows if row["track"] == "valence_coarse"],
        key=lambda item: float(item["value"]),
    )
    report = {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "research_hypothesis": "Polar RR/ACC features should improve arousal and potentially stabilize exploratory valence when fused with watch context.",
        "variants": [
            {
                "variant_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "input_modalities": list(item.input_modalities),
                "modality_group": item.modality_group,
                "description": item.description,
            }
            for item in variants
        ],
        "targets": [
            "arousal_coarse",
            "arousal_ordinal",
            "valence_coarse",
            "valence_ordinal_exploratory",
        ],
        "tracks": {
            result["variant_name"]: {
                "arousal_coarse": result["tracks"]["arousal_coarse"],
                "arousal_ordinal": result["tracks"]["arousal_ordinal"],
                "valence_coarse": result["tracks"]["valence_coarse"],
                "valence_ordinal": result["tracks"]["valence_ordinal"],
            }
            for result in variant_results
        },
        "comparison_summary": {
            "winner_arousal_coarse": winner_arousal,
            "winner_valence_coarse": winner_valence,
        },
        "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        "model_comparison": comparison_rows,
        "generated_at_utc": timestamp.isoformat(),
    }

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_e2_3_predictions_csv(path=predictions_path, rows=prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_per_subject_metrics_csv(path=per_subject_path, rows=per_subject_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_model_comparison_csv(path=comparison_path, rows=comparison_rows)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_e2_3_research_report_markdown(
            report=report,
            comparison_rows=comparison_rows,
            per_subject_rows=per_subject_rows,
        ),
        encoding="utf-8",
    )

    _generate_e2_3_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        per_subject_rows=per_subject_rows,
        variant_results=variant_results,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "examples_total": len(examples),
        "variant_count": len(variants),
    }


def run_m7_3_polar_first_training_dataset_build(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = _build_m7_3_polar_first_variants()
    variant_results = [_evaluate_polar_first_variant(examples=examples, variant=item) for item in variants]
    timestamp = datetime.now(timezone.utc)
    experiment_id = f"m7-3-polar-first-training-dataset-build-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"

    output_root = paths.output_dir / dataset_id / dataset_version / "m7-3-polar-first-training-dataset-build"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    test_examples = [item for item in examples if item.split == "test"]
    comparison_rows = _build_m7_3_model_comparison_rows(
        variant_results=variant_results,
        test_examples=test_examples,
        baseline_variant_name="polar_only",
    )
    per_subject_rows = [row for result in variant_results for row in result.per_subject_rows]
    prediction_rows = [row for result in variant_results for row in result.prediction_rows]
    anti_collapse_summary = _build_anti_collapse_summary(variant_results)

    report = _build_m7_3_report(
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        preprocessing_version=preprocessing_version,
        split_manifest=split_manifest,
        labels=labels,
        min_confidence=min_confidence,
        examples=examples,
        variants=variants,
        variant_results=variant_results,
        comparison_rows=comparison_rows,
        anti_collapse_summary=anti_collapse_summary,
        generated_at=timestamp,
    )

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_m7_3_predictions_csv(predictions_path, prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_per_subject_metrics_csv(path=per_subject_path, rows=per_subject_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_m7_3_model_comparison_csv(comparison_path, comparison_rows)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_m7_3_research_report_markdown(
            report=report,
            comparison_rows=comparison_rows,
            per_subject_rows=per_subject_rows,
        ),
        encoding="utf-8",
    )

    _generate_m7_3_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        per_subject_rows=per_subject_rows,
        variant_results=variant_results,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "examples_total": len(examples),
        "variant_count": len(variants),
    }


def run_m7_4_runtime_candidate_gate(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    del preprocessing_version, min_confidence

    m7_3_root = paths.output_dir / dataset_id / dataset_version / "m7-3-polar-first-training-dataset-build"
    m7_3_report_path = m7_3_root / "evaluation-report.json"
    if not m7_3_report_path.exists():
        raise FileNotFoundError(f"M7.4 requires M7.3 report at {m7_3_report_path}")

    with m7_3_report_path.open("r", encoding="utf-8") as handle:
        report = json.load(handle)

    winners_by_track = report.get("comparison_summary", {}).get("winner_by_track", {})
    comparison_rows = list(report.get("model_comparison") or [])
    anti_collapse_summary = report.get("anti_collapse_summary", {})
    flagged_rows = list(anti_collapse_summary.get("flagged_rows") or [])

    selected_winners_by_track: dict[str, dict[str, Any]] = {}
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        track_rows = [row for row in comparison_rows if row.get("track") == track_name]
        if track_rows:
            selected_winners_by_track[track_name] = _select_m7_3_winner_row(track_rows)

    winner_rows: list[dict[str, Any]] = []
    track_failures: list[dict[str, Any]] = []
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        winner = selected_winners_by_track.get(track_name) or winners_by_track.get(track_name) or {}
        row = {
            "track": track_name,
            "variant_name": winner.get("variant_name"),
            "model_family": winner.get("model_family"),
            "classifier_kind": winner.get("classifier_kind"),
            "modality_group": winner.get("modality_group"),
            "value": winner.get("value"),
            "claim_status": winner.get("claim_status"),
            "anti_collapse_status": winner.get("anti_collapse_status"),
        }
        winner_rows.append(row)

        track_issues: list[str] = []
        if row["variant_name"] is None:
            track_issues.append("missing_winner")
        if row["anti_collapse_status"] != "ok":
            track_issues.append("anti_collapse_not_ok")
        if row["claim_status"] not in {"supported"}:
            track_issues.append("claim_not_supported")
        if track_issues:
            track_failures.append(
                {
                    "track": track_name,
                    "issues": track_issues,
                    "winner": row,
                }
            )

    global_issues: list[str] = []
    if not anti_collapse_summary.get("passed", False):
        global_issues.append("anti_collapse_summary_failed")
    if flagged_rows:
        global_issues.append("flagged_rows_present")

    gate_passed = not track_failures and not global_issues
    verdict = "pass" if gate_passed else "fail"

    remediation_actions: list[dict[str, Any]] = []
    if not gate_passed:
        remediation_actions.append(
            {
                "action": "retrain_or_rebalance_flagged_tracks",
                "reason": "anti-collapse gate failed on at least one variant/track",
                "blocked_step": "P5 Runtime Bundle Export",
            }
        )
        for item in flagged_rows:
            remediation_actions.append(
                {
                    "action": "targeted_remediation_for_variant_track",
                    "variant_name": item.get("variant_name"),
                    "track": item.get("track"),
                    "issue": item.get("status"),
                    "dominant_share": item.get("dominant_share"),
                }
            )

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"m7-4-runtime-candidate-gate-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = paths.output_dir / dataset_id / dataset_version / "m7-4-runtime-candidate-gate"
    output_root.mkdir(parents=True, exist_ok=True)

    verdict_payload = {
        "experiment_id": experiment_id,
        "run_kind": "m7-4-runtime-candidate-gate",
        "source_report_path": str(m7_3_report_path),
        "source_experiment_id": report.get("experiment_id"),
        "gate_verdict": verdict,
        "gate_passed": gate_passed,
        "track_winners": winner_rows,
        "track_failures": track_failures,
        "global_issues": global_issues,
        "anti_collapse_summary": {
            "passed": anti_collapse_summary.get("passed"),
            "threshold": anti_collapse_summary.get("threshold"),
            "flagged_rows": flagged_rows,
        },
        "remediation_actions": remediation_actions,
        "next_step_if_pass": "P5 Runtime Bundle Export",
        "next_step_if_fail": "P4 remediation loop",
        "generated_at_utc": timestamp.isoformat(),
    }

    verdict_path = output_root / "runtime-candidate-verdict.json"
    verdict_path.write_text(json.dumps(verdict_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_md_path = output_root / "runtime-candidate-report.md"
    report_md_path.write_text(_build_m7_4_runtime_candidate_report(verdict_payload), encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(verdict_path),
        "research_report_path": str(report_md_path),
        "gate_verdict": verdict,
        "gate_passed": gate_passed,
        "output_root": str(output_root),
    }


def run_m7_5_runtime_bundle_export(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
    runtime_candidate_verdict_path: Path | None = None,
) -> dict[str, Any]:
    del preprocessing_version

    if runtime_candidate_verdict_path is None:
        runtime_candidate_verdict_path = (
            paths.output_dir / dataset_id / dataset_version / "m7-4-runtime-candidate-gate" / "runtime-candidate-verdict.json"
        )

    if not runtime_candidate_verdict_path.exists():
        raise FileNotFoundError(f"M7.5 requires M7.4 verdict at {runtime_candidate_verdict_path}")

    verdict = json.loads(runtime_candidate_verdict_path.read_text(encoding="utf-8"))
    gate_passed = bool(verdict.get("gate_passed", False))
    gate_verdict = str(verdict.get("gate_verdict", "unknown"))
    if not gate_passed:
        raise RuntimeError(
            "M7.5 runtime bundle export requires gate_passed=true; "
            f"found gate_passed={gate_passed!r} gate_verdict={gate_verdict!r} at {runtime_candidate_verdict_path}"
        )

    track_winners = verdict.get("track_winners")
    if not isinstance(track_winners, list):
        raise ValueError(f"invalid runtime candidate verdict track_winners: {runtime_candidate_verdict_path}")
    winners_by_track = {str(item.get("track")): item for item in track_winners if isinstance(item, dict)}

    candidate_specs = {item.variant_name: item for item in _build_m7_3_polar_first_variants()}
    selected_specs: dict[str, VariantSpec] = {}
    selected_winners: list[dict[str, Any]] = []
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        winner = winners_by_track.get(track_name)
        if not winner or not str(winner.get("variant_name") or ""):
            raise RuntimeError(f"M7.5 requires a winner for track {track_name}")
        variant_name = str(winner["variant_name"])
        spec = candidate_specs.get(variant_name)
        if spec is None:
            raise RuntimeError(f"M7.5 does not know how to export runtime candidate variant {variant_name!r}")
        selected_specs[track_name] = spec
        selected_winners.append(
            {
                "track": track_name,
                "variant_name": variant_name,
                "model_family": winner.get("model_family"),
                "classifier_kind": winner.get("classifier_kind"),
                "modality_group": winner.get("modality_group"),
                "value": winner.get("value"),
                "claim_status": winner.get("claim_status"),
                "anti_collapse_status": winner.get("anti_collapse_status"),
            }
        )

    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    test_examples = [item for item in examples if item.split == "test"]
    fit_examples = train_examples + validation_examples
    if not fit_examples or not test_examples:
        raise ValueError("M7.5 requires non-empty train+validation fit split and test split")

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"m7-5-runtime-bundle-export-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = paths.output_dir / dataset_id / dataset_version / "m7-5-runtime-bundle-export"
    output_root.mkdir(parents=True, exist_ok=True)

    bundle_id = "on-go-m7-5-runtime-bundle-export"
    bundle_version = "v1"
    required_live_streams = ["watch_accelerometer", "polar_hr"]
    optional_live_streams = ["watch_heart_rate", "polar_rr", "watch_activity_context", "watch_hrv"]
    notes = (
        "M7.5 runtime export built from M7.4 approved candidates; "
        "track models are trained on train+validation and smoke-tested on held-out test split."
    )

    track_exports: dict[str, dict[str, Any]] = {}
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        track_exports[track_name] = _export_runtime_bundle_track(
            output_dir=output_root,
            examples=examples,
            fit_examples=fit_examples,
            test_examples=test_examples,
            variant_spec=selected_specs[track_name],
            target_field=_runtime_bundle_target_field(track_name),
            track_name=track_name,
        )

    manifest_payload = _build_runtime_bundle_manifest_payload(
        bundle_id=bundle_id,
        bundle_version=bundle_version,
        required_live_streams=required_live_streams,
        optional_live_streams=optional_live_streams,
        notes=notes,
        track_exports=track_exports,
        output_dir=output_root,
    )
    manifest_path = output_root / "model-bundle.manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    export_report = {
        "experiment_id": experiment_id,
        "run_kind": "m7-5-runtime-bundle-export",
        "source_verdict_path": str(runtime_candidate_verdict_path),
        "source_experiment_id": verdict.get("source_experiment_id"),
        "gate_verdict": gate_verdict,
        "gate_passed": gate_passed,
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "manifest_path": str(manifest_path),
        "output_root": str(output_root),
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "track_exports": [
            {
                "track": track_name,
                "variant_name": payload["variant_name"],
                "model_family": payload["model_family"],
                "classifier_kind": payload["classifier_kind"],
                "modality_group": payload["modality_group"],
                "feature_count": payload["feature_count"],
                "feature_profile": payload["feature_profile"],
                "model_path": payload["model_path"],
                "feature_names_path": payload["feature_names_path"],
                "fit_split_subjects": payload["fit_split_subjects"],
                "test_split_subjects": payload["test_split_subjects"],
            }
            for track_name, payload in sorted(track_exports.items())
        ],
        "track_winners": selected_winners,
        "generated_at_utc": timestamp.isoformat(),
        "notes": notes,
    }
    export_report_path = output_root / "runtime-bundle-export-report.json"
    export_report_path.write_text(json.dumps(export_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    smoke_summary = _build_runtime_bundle_smoke_summary(
        output_root=output_root,
        manifest_path=manifest_path,
        track_exports=track_exports,
        test_examples=test_examples,
    )
    smoke_summary.update(
        {
            "experiment_id": experiment_id,
            "run_kind": "m7-5-runtime-bundle-export",
            "source_verdict_path": str(runtime_candidate_verdict_path),
            "source_experiment_id": verdict.get("source_experiment_id"),
            "bundle_id": bundle_id,
            "bundle_version": bundle_version,
            "generated_at_utc": timestamp.isoformat(),
        }
    )
    smoke_summary_path = output_root / "runtime-bundle-smoke-summary.json"
    smoke_summary_path.write_text(json.dumps(smoke_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(export_report_path),
        "research_report_path": str(smoke_summary_path),
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "gate_passed": gate_passed,
        "gate_verdict": gate_verdict,
        "track_exports": export_report["track_exports"],
    }


def run_m7_9_polar_expanded_fusion_benchmark(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = _build_m7_9_polar_expanded_variants()
    variant_results = [_evaluate_polar_first_variant(examples=examples, variant=item) for item in variants]
    timestamp = datetime.now(timezone.utc)
    experiment_id = f"m7-9-polar-expanded-fusion-benchmark-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"

    output_root = paths.output_dir / dataset_id / dataset_version / "m7-9-polar-expanded-fusion-benchmark"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    test_examples = [item for item in examples if item.split == "test"]
    comparison_rows = _build_m7_3_model_comparison_rows(
        variant_results=variant_results,
        test_examples=test_examples,
        baseline_variant_name="polar_cardio_only",
    )
    per_subject_rows = [row for result in variant_results for row in result.per_subject_rows]
    prediction_rows = [row for result in variant_results for row in result.prediction_rows]
    anti_collapse_summary = _build_anti_collapse_summary(variant_results)

    report = _build_m7_9_report(
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        preprocessing_version=preprocessing_version,
        split_manifest=split_manifest,
        labels=labels,
        min_confidence=min_confidence,
        examples=examples,
        variants=variants,
        variant_results=variant_results,
        comparison_rows=comparison_rows,
        anti_collapse_summary=anti_collapse_summary,
        generated_at=timestamp,
    )

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_m7_3_predictions_csv(predictions_path, prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_per_subject_metrics_csv(path=per_subject_path, rows=per_subject_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_m7_3_model_comparison_csv(comparison_path, comparison_rows)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_m7_9_research_report_markdown(
            report=report,
            comparison_rows=comparison_rows,
            per_subject_rows=per_subject_rows,
        ),
        encoding="utf-8",
    )

    _generate_m7_9_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        per_subject_rows=per_subject_rows,
        variant_results=variant_results,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "examples_total": len(examples),
        "variant_count": len(variants),
    }


def run_m7_9_runtime_bundle_export(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
    track_variant_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    del preprocessing_version

    benchmark_root = paths.output_dir / dataset_id / dataset_version / "m7-9-polar-expanded-fusion-benchmark"
    benchmark_report_path = benchmark_root / "evaluation-report.json"
    if not benchmark_report_path.exists():
        raise FileNotFoundError(f"M7.9 bundle export requires benchmark report at {benchmark_report_path}")

    benchmark_report = json.loads(benchmark_report_path.read_text(encoding="utf-8"))
    winners = benchmark_report.get("comparison_summary", {}).get("winner_by_track") or {}
    if not isinstance(winners, dict):
        raise ValueError(f"invalid winner_by_track block in {benchmark_report_path}")

    variant_specs = {item.variant_name: item for item in _build_m7_9_polar_expanded_variants()}
    overrides = {k: v for k, v in (track_variant_overrides or {}).items() if v}
    valid_tracks = {"activity", "arousal_coarse", "valence_coarse"}
    for track_key, variant_name in overrides.items():
        if track_key not in valid_tracks:
            raise ValueError(f"unknown M7.9 track in track_variant_overrides: {track_key!r}")
        if variant_name not in variant_specs:
            raise ValueError(
                f"unknown M7.9 variant {variant_name!r} for track {track_key}; "
                f"expected one of {sorted(variant_specs)}",
            )

    selected_specs: dict[str, VariantSpec] = {}
    selected_winners: list[dict[str, Any]] = []
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        override_name = overrides.get(track_name)
        if override_name:
            spec = variant_specs[override_name]
            selected_specs[track_name] = spec
            selected_winners.append(
                {
                    "track": track_name,
                    "variant_name": override_name,
                    "model_family": spec.model_family,
                    "classifier_kind": spec.classifier_kind,
                    "modality_group": spec.modality_group,
                    "value": None,
                    "claim_status": None,
                    "anti_collapse_status": None,
                    "selection": "override",
                    "benchmark_winner": winners.get(track_name),
                }
            )
            continue

        winner = winners.get(track_name)
        if not isinstance(winner, dict):
            raise RuntimeError(f"M7.9 bundle export requires winner for track {track_name}")
        variant_name = str(winner.get("variant_name") or "")
        if not variant_name:
            raise RuntimeError(f"M7.9 bundle export requires non-empty winner variant for track {track_name}")
        spec = variant_specs.get(variant_name)
        if spec is None:
            raise RuntimeError(f"M7.9 bundle export does not know variant {variant_name!r}")
        selected_specs[track_name] = spec
        selected_winners.append(
            {
                "track": track_name,
                "variant_name": variant_name,
                "model_family": winner.get("model_family"),
                "classifier_kind": winner.get("classifier_kind"),
                "modality_group": winner.get("modality_group"),
                "value": winner.get("value"),
                "claim_status": winner.get("claim_status"),
                "anti_collapse_status": winner.get("anti_collapse_status"),
                "selection": "benchmark",
            }
        )

    examples, _, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    test_examples = [item for item in examples if item.split == "test"]
    fit_examples = train_examples + validation_examples
    if not fit_examples or not test_examples:
        raise ValueError("M7.9 bundle export requires non-empty train+validation fit split and test split")

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"m7-9-runtime-bundle-export-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = paths.output_dir / dataset_id / dataset_version / "m7-9-runtime-bundle-export"
    output_root.mkdir(parents=True, exist_ok=True)

    bundle_id = "on-go-m7-9-polar-expanded-runtime-bundle"
    bundle_version = "v3" if overrides else "v2"
    required_live_streams = ["watch_accelerometer", "polar_hr", "polar_rr"]
    optional_live_streams = ["watch_heart_rate", "watch_activity_context", "watch_hrv"]
    notes = (
        "M7.9 runtime export built from polar-expanded benchmark winners; "
        "bundle expects polar_rr as required cardio stream for policy-compliant live serving."
    )
    if overrides:
        notes = (
            notes
            + " Track variant overrides applied: "
            + ", ".join(f"{k}={v}" for k, v in sorted(overrides.items()))
            + "."
        )

    track_exports: dict[str, dict[str, Any]] = {}
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        track_exports[track_name] = _export_runtime_bundle_track(
            output_dir=output_root,
            examples=examples,
            fit_examples=fit_examples,
            test_examples=test_examples,
            variant_spec=selected_specs[track_name],
            target_field=_runtime_bundle_target_field(track_name),
            track_name=track_name,
            feature_profile_prefix="m7-9",
        )

    manifest_payload = _build_runtime_bundle_manifest_payload(
        bundle_id=bundle_id,
        bundle_version=bundle_version,
        required_live_streams=required_live_streams,
        optional_live_streams=optional_live_streams,
        notes=notes,
        track_exports=track_exports,
        output_dir=output_root,
    )
    manifest_path = output_root / "model-bundle.manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    export_report = {
        "experiment_id": experiment_id,
        "run_kind": "m7-9-runtime-bundle-export",
        "source_report_path": str(benchmark_report_path),
        "source_experiment_id": benchmark_report.get("experiment_id"),
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "track_variant_overrides": overrides or None,
        "manifest_path": str(manifest_path),
        "output_root": str(output_root),
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "track_exports": [
            {
                "track": track_name,
                "variant_name": payload["variant_name"],
                "model_family": payload["model_family"],
                "classifier_kind": payload["classifier_kind"],
                "modality_group": payload["modality_group"],
                "feature_count": payload["feature_count"],
                "feature_profile": payload["feature_profile"],
                "model_path": payload["model_path"],
                "feature_names_path": payload["feature_names_path"],
                "fit_split_subjects": payload["fit_split_subjects"],
                "test_split_subjects": payload["test_split_subjects"],
            }
            for track_name, payload in sorted(track_exports.items())
        ],
        "track_winners": selected_winners,
        "generated_at_utc": timestamp.isoformat(),
        "notes": notes,
    }
    export_report_path = output_root / "runtime-bundle-export-report.json"
    export_report_path.write_text(json.dumps(export_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    smoke_summary = _build_runtime_bundle_smoke_summary(
        output_root=output_root,
        manifest_path=manifest_path,
        track_exports=track_exports,
        test_examples=test_examples,
    )
    smoke_summary.update(
        {
            "experiment_id": experiment_id,
            "run_kind": "m7-9-runtime-bundle-export",
            "source_report_path": str(benchmark_report_path),
            "source_experiment_id": benchmark_report.get("experiment_id"),
            "bundle_id": bundle_id,
            "bundle_version": bundle_version,
            "generated_at_utc": timestamp.isoformat(),
        }
    )
    smoke_summary_path = output_root / "runtime-bundle-smoke-summary.json"
    smoke_summary_path.write_text(json.dumps(smoke_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(export_report_path),
        "research_report_path": str(smoke_summary_path),
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "track_exports": export_report["track_exports"],
    }


def _export_runtime_bundle_track(
    *,
    output_dir: Path,
    examples: list[SegmentExample],
    fit_examples: list[SegmentExample],
    test_examples: list[SegmentExample],
    variant_spec: VariantSpec,
    target_field: str,
    track_name: str,
    feature_profile_prefix: str = "m7-5",
) -> dict[str, Any]:
    all_feature_names = sorted(examples[0].features.keys())
    feature_names = _select_feature_names(all_feature_names, variant_spec.feature_prefixes)
    if not feature_names:
        raise ValueError(f"runtime bundle track {track_name} has no feature set")

    x_fit = _to_feature_matrix(fit_examples, feature_names)
    x_test = _to_feature_matrix(test_examples, feature_names)
    y_fit = [str(getattr(item, target_field)) for item in fit_examples]
    y_test = [str(getattr(item, target_field)) for item in test_examples]

    classifier = _build_classifier(variant_spec.classifier_kind)
    classifier.fit(x_fit, y_fit)
    test_pred = [str(item) for item in classifier.predict(x_test)]
    test_metrics = compute_classification_metrics(y_test, test_pred)
    feature_profile = f"{feature_profile_prefix}-{variant_spec.variant_name}"

    model_path = output_dir / _runtime_bundle_track_model_filename(
        track_name=track_name,
        variant_name=variant_spec.variant_name,
        classifier_kind=variant_spec.classifier_kind,
    )
    feature_names_path = output_dir / f"{track_name}_feature_names.json"
    joblib.dump(classifier, model_path)
    feature_names_path.write_text(
        json.dumps({"feature_names": feature_names}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "track": track_name,
        "variant_name": variant_spec.variant_name,
        "model_family": variant_spec.model_family,
        "classifier_kind": variant_spec.classifier_kind,
        "modality_group": variant_spec.modality_group,
        "feature_profile": feature_profile,
        "model_path": str(model_path),
        "feature_names_path": str(feature_names_path),
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "fit_split_subjects": sorted({item.subject_id for item in fit_examples}),
        "test_split_subjects": sorted({item.subject_id for item in test_examples}),
        "test_segment_count": len(test_examples),
        "test_metrics": {
            "macro_f1": test_metrics.macro_f1,
            "balanced_accuracy": test_metrics.balanced_accuracy,
            "weighted_f1": test_metrics.weighted_f1,
            "macro_recall": test_metrics.macro_recall,
            "labels": test_metrics.labels,
            "per_class_support": test_metrics.per_class_support,
            "confusion_matrix": test_metrics.confusion_matrix,
        },
        "test_prediction_count": len(test_pred),
        "test_predicted_class_count": len({item for item in test_pred if item}),
        "test_dominant_share": _dominant_share(test_pred),
        "target_field": target_field,
    }


def _runtime_bundle_target_field(track_name: str) -> str:
    if track_name == "activity":
        return "activity_label"
    if track_name == "arousal_coarse":
        return "arousal_coarse"
    if track_name == "valence_coarse":
        return "valence_coarse"
    raise ValueError(f"unsupported runtime bundle track: {track_name}")


def _runtime_bundle_track_model_filename(*, track_name: str, variant_name: str, classifier_kind: str) -> str:
    del classifier_kind
    return f"{track_name}_{_runtime_bundle_token(variant_name)}.joblib"


def _runtime_bundle_token(value: str) -> str:
    return value.replace("+", "_plus_").replace(" ", "_")


def _manifest_relative_path(output_dir: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(output_dir.resolve()))
    except ValueError:
        return str(resolved)


def _runtime_bundle_track_block(
    *,
    output_dir: Path,
    model_path: Path,
    feature_names_path: Path,
    classifier_kind: str,
    feature_profile: str,
    modality_group: str,
    policy_scope: str | None = None,
) -> dict[str, str]:
    block: dict[str, str] = {
        "model_path": _manifest_relative_path(output_dir, model_path),
        "feature_names_path": _manifest_relative_path(output_dir, feature_names_path),
        "classifier_kind": classifier_kind,
        "feature_profile": feature_profile,
        "modality_group": modality_group,
    }
    if policy_scope:
        block["policy_scope"] = policy_scope
    return block


def _build_runtime_bundle_manifest_payload(
    *,
    bundle_id: str,
    bundle_version: str,
    required_live_streams: list[str],
    optional_live_streams: list[str],
    notes: str,
    track_exports: dict[str, dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    direct_outputs: dict[str, Any] = {}
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        export = track_exports[track_name]
        direct_outputs[track_name] = _runtime_bundle_track_block(
            output_dir=output_dir,
            model_path=Path(export["model_path"]),
            feature_names_path=Path(export["feature_names_path"]),
            classifier_kind=str(export["classifier_kind"]),
            feature_profile=str(export["feature_profile"]),
            modality_group=str(export["modality_group"]),
        )

    return {
        "manifest_version": "1.0.0",
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "required_live_streams": required_live_streams,
        "optional_live_streams": optional_live_streams,
        "direct_outputs": direct_outputs,
        "notes": notes,
    }


def _build_runtime_bundle_smoke_summary(
    *,
    output_root: Path,
    manifest_path: Path,
    track_exports: dict[str, dict[str, Any]],
    test_examples: list[SegmentExample],
) -> dict[str, Any]:
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    direct_outputs = raw_manifest.get("direct_outputs")
    if not isinstance(direct_outputs, dict):
        raise ValueError(f"invalid runtime bundle manifest direct_outputs: {manifest_path}")

    smoke_tracks: list[dict[str, Any]] = []
    for track_name, export in sorted(track_exports.items()):
        block = direct_outputs.get(track_name)
        if not isinstance(block, dict):
            raise ValueError(f"manifest missing track block: {track_name}")
        model_path = _resolve_runtime_bundle_manifest_path(manifest_path, block.get("model_path"), track_name, "model_path")
        feature_names_path = _resolve_runtime_bundle_manifest_path(
            manifest_path,
            block.get("feature_names_path"),
            track_name,
            "feature_names_path",
        )
        model = joblib.load(model_path)
        feature_names = _load_runtime_bundle_feature_names(feature_names_path)
        if feature_names != export["feature_names"]:
            raise ValueError(f"runtime bundle feature names mismatch for {track_name}")

        x_test = _to_feature_matrix(test_examples, feature_names)
        target_field = _runtime_bundle_target_field(track_name)
        y_test = [str(getattr(item, target_field)) for item in test_examples]
        y_pred = [str(item) for item in model.predict(x_test)]
        metrics = compute_classification_metrics(y_test, y_pred)
        smoke_tracks.append(
            {
                "track": track_name,
                "variant_name": export["variant_name"],
                "model_path": str(model_path),
                "feature_names_path": str(feature_names_path),
                "feature_count": len(feature_names),
                "predicted_class_count": len({item for item in y_pred if item}),
                "dominant_share": _dominant_share(y_pred),
                "macro_f1": metrics.macro_f1,
                "balanced_accuracy": metrics.balanced_accuracy,
            }
        )

    return {
        "passed": True,
        "output_root": str(output_root),
        "manifest_path": str(manifest_path),
        "manifest_version": str(raw_manifest.get("manifest_version", "1.0.0")),
        "bundle_id": str(raw_manifest.get("bundle_id", output_root.name)),
        "bundle_version": str(raw_manifest.get("bundle_version", "v1")),
        "track_count": len(smoke_tracks),
        "track_summaries": smoke_tracks,
        "manifest_direct_outputs": sorted(direct_outputs.keys()),
    }


def _resolve_runtime_bundle_manifest_path(
    manifest_path: Path,
    raw_value: object,
    track_name: str,
    field_name: str,
) -> Path:
    if not isinstance(raw_value, str) or not raw_value:
        raise ValueError(f"manifest field missing for {track_name}.{field_name}")
    return (manifest_path.parent / raw_value).resolve()


def _load_runtime_bundle_feature_names(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    feature_names = raw.get("feature_names")
    if not isinstance(feature_names, list) or not all(isinstance(item, str) for item in feature_names):
        raise ValueError(f"invalid feature_names payload: {path}")
    return [str(item) for item in feature_names]


def _dominant_share(predictions: list[str]) -> float:
    if not predictions:
        return 0.0
    counts = Counter(str(item) for item in predictions)
    dominant_count = max(counts.values()) if counts else 0
    return round(float(dominant_count) / float(len(predictions)), 6)


def run_g3_1_wesad_extended_model_zoo(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = _build_extended_model_zoo_variants()
    variant_results: list[VariantRunResult] = []
    failed_variants: list[FailedVariantRun] = []
    for variant in variants:
        try:
            variant_results.append(_evaluate_variant(examples=examples, variant=variant))
        except Exception as exc:
            failed_variants.append(
                FailedVariantRun(
                    variant_name=variant.variant_name,
                    model_family=variant.model_family,
                    classifier_kind=variant.classifier_kind,
                    modality_group=variant.modality_group,
                    input_modalities=list(variant.input_modalities),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

    if not variant_results:
        raise RuntimeError("all G3.1 variants failed")
    if not any(item.variant_name == "watch_only_centroid" for item in variant_results):
        raise RuntimeError("G3.1 requires watch_only_centroid as successful baseline reference")

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"g3-1-model-zoo-wesad-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"

    output_root = paths.output_dir / dataset_id / dataset_version / "model-zoo-benchmark"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    test_examples = [item for item in examples if item.split == "test"]
    comparison_rows = _build_extended_model_comparison_rows(
        variant_results=variant_results,
        test_examples=test_examples,
        global_baseline_name="watch_only_centroid",
    )
    prediction_rows = _extended_prediction_rows(examples=examples, variant_results=variant_results)
    per_subject_rows = _extended_per_subject_rows(variant_results=variant_results)
    feature_importance_rows = [row for result in variant_results for row in result.feature_importance_rows]
    previous_reference = _load_previous_g3_reference(
        paths.output_dir / dataset_id / dataset_version / "comparison" / "evaluation-report.json"
    )

    report = _build_model_zoo_report(
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        preprocessing_version=preprocessing_version,
        split_manifest=split_manifest,
        labels=labels,
        min_confidence=min_confidence,
        variants=variants,
        variant_results=variant_results,
        failed_variants=failed_variants,
        comparison_rows=comparison_rows,
        previous_reference=previous_reference,
        generated_at=timestamp,
        examples=examples,
    )

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_extended_predictions_csv(path=predictions_path, rows=prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_extended_per_subject_metrics_csv(path=per_subject_path, rows=per_subject_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_extended_model_comparison_csv(path=comparison_path, rows=comparison_rows)

    feature_importance_path = output_root / "feature-importance.csv"
    _write_feature_importance_csv(path=feature_importance_path, rows=feature_importance_rows)

    failed_variants_path = output_root / "failed-variants.csv"
    _write_failed_variants_csv(path=failed_variants_path, rows=failed_variants)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_model_zoo_report_markdown(
            report=report,
            comparison_rows=comparison_rows,
            variant_results=variant_results,
            feature_importance_rows=feature_importance_rows,
            previous_reference=previous_reference,
        ),
        encoding="utf-8",
    )

    _generate_model_zoo_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        per_subject_rows=per_subject_rows,
        feature_importance_rows=feature_importance_rows,
        variant_results=variant_results,
        test_examples=test_examples,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "feature_importance_path": str(feature_importance_path),
        "failed_variants_path": str(failed_variants_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "examples_total": len(examples),
        "successful_variant_count": len(variant_results),
        "failed_variant_count": len(failed_variants),
    }


def run_g3_1_wesad_loso(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    subjects = sorted({item.subject_id for item in examples})
    if len(subjects) < 3:
        raise ValueError("LOSO requires at least 3 subjects")

    variants = _build_extended_model_zoo_variants()
    fold_metrics_rows: list[dict[str, Any]] = []
    failed_variants: list[dict[str, Any]] = []
    variant_fold_scores: dict[tuple[str, str], list[tuple[int, float]]] = {}
    variant_meta: dict[str, dict[str, Any]] = {}
    expected_fold_count = len(subjects)

    for fold_id, test_subject_id in enumerate(subjects, start=1):
        validation_subject_id = subjects[fold_id % len(subjects)]
        fold_examples = _loso_fold_examples(
            examples=examples,
            test_subject_id=test_subject_id,
            validation_subject_id=validation_subject_id,
        )
        for variant in variants:
            try:
                result = _evaluate_variant(examples=fold_examples, variant=variant)
            except Exception as exc:
                failed_variants.append(
                    {
                        "fold_id": fold_id,
                        "test_subject_id": test_subject_id,
                        "validation_subject_id": validation_subject_id,
                        "variant_name": variant.variant_name,
                        "model_family": variant.model_family,
                        "classifier_kind": variant.classifier_kind,
                        "modality_group": variant.modality_group,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                continue

            variant_meta[variant.variant_name] = {
                "variant_name": variant.variant_name,
                "model_family": result.model_family,
                "classifier_kind": result.classifier_kind,
                "modality_group": result.modality_group,
                "feature_count": len(result.feature_names),
            }
            for track_name in ("activity", "arousal_coarse"):
                value = float(result.tracks[track_name]["test"]["macro_f1"])
                variant_fold_scores.setdefault((variant.variant_name, track_name), []).append((fold_id, value))
                fold_metrics_rows.append(
                    {
                        "fold_id": fold_id,
                        "test_subject_id": test_subject_id,
                        "validation_subject_id": validation_subject_id,
                        "variant_name": variant.variant_name,
                        "model_family": result.model_family,
                        "classifier_kind": result.classifier_kind,
                        "modality_group": result.modality_group,
                        "track": track_name,
                        "metric_name": "macro_f1",
                        "value": round(value, 6),
                    }
                )

    if not any(row["variant_name"] == "watch_only_centroid" for row in fold_metrics_rows):
        raise RuntimeError("G3.1 LOSO requires watch_only_centroid baseline across folds")

    comparison_rows = _build_loso_model_comparison_rows(
        variant_fold_scores=variant_fold_scores,
        variant_meta=variant_meta,
        expected_fold_count=expected_fold_count,
        baseline_variant_name="watch_only_centroid",
    )
    if not comparison_rows:
        raise RuntimeError("no successful LOSO model comparisons")

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"g3-1-model-zoo-wesad-loso-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = paths.output_dir / dataset_id / dataset_version / "model-zoo-benchmark-loso"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    winners = {}
    for track_name in ("activity", "arousal_coarse"):
        track_rows = [row for row in comparison_rows if row["track"] == track_name]
        if not track_rows:
            continue
        best = max(track_rows, key=lambda item: float(item["mean_macro_f1"]))
        winners[track_name] = {
            "variant_name": best["variant_name"],
            "model_family": best["model_family"],
            "classifier_kind": best["classifier_kind"],
            "modality_group": best["modality_group"],
            "mean_macro_f1": best["mean_macro_f1"],
            "std_macro_f1": best["std_macro_f1"],
            "ci95_low": best["ci95_low"],
            "ci95_high": best["ci95_high"],
            "delta_vs_watch_only": best["delta_vs_watch_only"],
            "claim_status": best["claim_status"],
        }

    report = {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "evaluation_mode": "leave-one-subject-out",
        "status": "baseline",
        "comparison_goal": "Benchmark extended model zoo under LOSO protocol for robust model selection.",
        "fold_count": expected_fold_count,
        "subjects_evaluated": subjects,
        "comparison_summary": {
            "winner_by_track": winners,
            "model_comparison": comparison_rows,
        },
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "subjects": len({item.subject_id for item in examples}),
            "sessions": len({item.session_id for item in examples}),
            "segments": len(examples),
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "failed_variants": failed_variants,
        "generated_at_utc": timestamp.isoformat(),
    }

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fold_metrics_path = output_root / "fold-metrics.csv"
    _write_g3_1_loso_fold_metrics_csv(fold_metrics_path, fold_metrics_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_g3_1_loso_model_comparison_csv(comparison_path, comparison_rows)

    failed_variants_path = output_root / "failed-variants.csv"
    _write_failed_variants_csv(path=failed_variants_path, rows=failed_variants)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_g3_1_loso_report_markdown(report=report, comparison_rows=comparison_rows),
        encoding="utf-8",
    )

    _generate_g3_1_loso_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        fold_metrics_rows=fold_metrics_rows,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "fold_metrics_path": str(fold_metrics_path),
        "model_comparison_path": str(comparison_path),
        "failed_variants_path": str(failed_variants_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "fold_count": expected_fold_count,
        "successful_variant_count": len({row["variant_name"] for row in comparison_rows}),
        "failed_variant_events": len(failed_variants),
    }


def run_h2_light_personalization_wesad(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
    calibration_segments: int = 2,
) -> dict[str, Any]:
    if calibration_segments < 1:
        raise ValueError("calibration_segments must be >= 1")

    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = [
        VariantSpec(
            variant_name="watch_only_ada_boost",
            model_family="adaboost",
            classifier_kind="ada_boost",
            feature_prefixes=("watch_",),
            input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
            description="Global watch-only candidate from G3.1 with light subject calibration.",
            modality_group="watch_only",
        ),
        VariantSpec(
            variant_name="watch_only_random_forest",
            model_family="random_forest",
            classifier_kind="random_forest",
            feature_prefixes=("watch_",),
            input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
            description="Alternative watch-only classical family for personalization robustness checks.",
            modality_group="watch_only",
        ),
        VariantSpec(
            variant_name="fusion_catboost",
            model_family="catboost_multiclass",
            classifier_kind="catboost",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Global fusion candidate from G3.1 with light subject calibration.",
            modality_group="fusion",
        ),
        VariantSpec(
            variant_name="fusion_gaussian_nb",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Fusion fallback family with light subject calibration.",
            modality_group="fusion",
        ),
    ]

    variant_results: list[LightPersonalizationVariantResult] = []
    failed_variants: list[FailedVariantRun] = []
    for variant in variants:
        try:
            variant_results.append(
                _evaluate_light_personalization_variant(
                    examples=examples,
                    variant=variant,
                    calibration_segments=calibration_segments,
                )
            )
        except Exception as exc:
            failed_variants.append(
                FailedVariantRun(
                    variant_name=variant.variant_name,
                    model_family=variant.model_family,
                    classifier_kind=variant.classifier_kind,
                    modality_group=variant.modality_group,
                    input_modalities=list(variant.input_modalities),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

    if not variant_results:
        raise RuntimeError("all H2 variants failed")

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"h2-light-personalization-wesad-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = paths.output_dir / dataset_id / dataset_version / "light-personalization"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    comparison_rows = _build_h2_model_comparison_rows(variant_results)
    prediction_rows = [row for result in variant_results for row in result.prediction_rows]
    per_subject_rows = [row for result in variant_results for row in result.per_subject_rows]
    budget_rows = [row for result in variant_results for row in result.budget_rows]

    winners: dict[str, dict[str, Any]] = {}
    for track in ("activity", "arousal_coarse"):
        personalized_rows = [
            row for row in comparison_rows if row["track"] == track and row["evaluation_mode"] == "personalized"
        ]
        best = max(personalized_rows, key=lambda item: float(item["value"]))
        winners[track] = {
            "variant_name": best["variant_name"],
            "model_family": best["model_family"],
            "classifier_kind": best["classifier_kind"],
            "modality_group": best["modality_group"],
            "value": best["value"],
            "delta_vs_global": best["delta_vs_global"],
            "claim_status": best["claim_status"],
        }

    report = {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "comparison_goal": "Compare global candidates against light personalization via subject-specific calibration mapping.",
        "research_hypothesis": "Light calibration without model fine-tuning should improve per-subject macro_f1 while controlling worst-case degradation.",
        "status": "baseline",
        "calibration_policy": {
            "calibration_segments_per_subject": calibration_segments,
            "adaptation_method": "subject-level post-hoc predicted->true label mapping from calibration subset",
            "leakage_guard": "subject calibration subset is disjoint from subject evaluation subset",
        },
        "variants": [
            {
                "variant_name": result.variant_name,
                "model_family": result.model_family,
                "classifier_kind": result.classifier_kind,
                "modality_group": result.modality_group,
                "input_modalities": result.input_modalities,
                "feature_count": len(result.feature_names),
                "split_summary": result.split_summary,
            }
            for result in variant_results
        ],
        "comparison_summary": {
            "winner_by_track": winners,
            "model_comparison": comparison_rows,
            "budget_sensitivity": budget_rows,
        },
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "evaluation_subset": "wesad unified labels with per-subject calibration split inside test subjects",
            "subjects": len({item.subject_id for item in examples}),
            "sessions": len({item.session_id for item in examples}),
            "segments": len(examples),
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "failed_variants": [
            {
                "variant_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "modality_group": item.modality_group,
                "error_type": item.error_type,
                "error_message": item.error_message,
            }
            for item in failed_variants
        ],
        "generated_at_utc": timestamp.isoformat(),
    }

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_h2_predictions_csv(predictions_path, prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_h2_per_subject_metrics_csv(per_subject_path, per_subject_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_h2_model_comparison_csv(comparison_path, comparison_rows)

    failed_variants_path = output_root / "failed-variants.csv"
    _write_failed_variants_csv(path=failed_variants_path, rows=failed_variants)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_h2_report_markdown(
            report=report,
            comparison_rows=comparison_rows,
            per_subject_rows=per_subject_rows,
            budget_rows=budget_rows,
        ),
        encoding="utf-8",
    )
    _generate_h2_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        per_subject_rows=per_subject_rows,
        budget_rows=budget_rows,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "failed_variants_path": str(failed_variants_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "successful_variant_count": len(variant_results),
        "failed_variant_count": len(failed_variants),
    }


def run_h3_full_personalization_wesad(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
    calibration_segments: int = 2,
    adaptation_weight: int = 5,
) -> dict[str, Any]:
    if calibration_segments < 1:
        raise ValueError("calibration_segments must be >= 1")
    if adaptation_weight < 1:
        raise ValueError("adaptation_weight must be >= 1")

    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = [
        VariantSpec(
            variant_name="watch_only_ada_boost",
            model_family="adaboost",
            classifier_kind="ada_boost",
            feature_prefixes=("watch_",),
            input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
            description="Watch-only candidate with full personalization refit.",
            modality_group="watch_only",
        ),
        VariantSpec(
            variant_name="watch_only_random_forest",
            model_family="random_forest",
            classifier_kind="random_forest",
            feature_prefixes=("watch_",),
            input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
            description="Watch-only classical family with full personalization refit.",
            modality_group="watch_only",
        ),
        VariantSpec(
            variant_name="fusion_catboost",
            model_family="catboost_multiclass",
            classifier_kind="catboost",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Fusion candidate with full personalization refit.",
            modality_group="fusion",
        ),
        VariantSpec(
            variant_name="fusion_gaussian_nb",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Fusion fallback family with full personalization refit.",
            modality_group="fusion",
        ),
    ]

    variant_results: list[FullPersonalizationVariantResult] = []
    failed_variants: list[FailedVariantRun] = []
    for variant in variants:
        try:
            variant_results.append(
                _evaluate_full_personalization_variant(
                    examples=examples,
                    variant=variant,
                    calibration_segments=calibration_segments,
                    adaptation_weight=adaptation_weight,
                )
            )
        except Exception as exc:
            failed_variants.append(
                FailedVariantRun(
                    variant_name=variant.variant_name,
                    model_family=variant.model_family,
                    classifier_kind=variant.classifier_kind,
                    modality_group=variant.modality_group,
                    input_modalities=list(variant.input_modalities),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

    if not variant_results:
        raise RuntimeError("all H3 variants failed")

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"h3-full-personalization-wesad-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = paths.output_dir / dataset_id / dataset_version / "full-personalization"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    comparison_rows = _build_h3_model_comparison_rows(variant_results)
    prediction_rows = [row for result in variant_results for row in result.prediction_rows]
    per_subject_rows = [row for result in variant_results for row in result.per_subject_rows]
    budget_rows = [row for result in variant_results for row in result.budget_rows]

    winners: dict[str, dict[str, Any]] = {}
    for track in ("activity", "arousal_coarse"):
        full_rows = [row for row in comparison_rows if row["track"] == track and row["evaluation_mode"] == "full"]
        best = max(full_rows, key=lambda item: float(item["value"]))
        winners[track] = {
            "variant_name": best["variant_name"],
            "model_family": best["model_family"],
            "classifier_kind": best["classifier_kind"],
            "modality_group": best["modality_group"],
            "value": best["value"],
            "delta_vs_global": best["delta_vs_global"],
            "delta_vs_light": best["delta_vs_light"],
            "claim_status": best["claim_status"],
        }

    report = {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "comparison_goal": "Compare global, light and full personalization under the same subject-level calibration protocol.",
        "research_hypothesis": "Full personalization (subject-specific refit) should improve over light personalization on difficult subjects while respecting degradation guardrails.",
        "status": "baseline",
        "calibration_policy": {
            "calibration_segments_per_subject": calibration_segments,
            "light_method": "subject-level post-hoc predicted->true mapping",
            "full_method": "subject-specific refit on global_train + repeated calibration samples",
            "full_adaptation_weight": adaptation_weight,
            "leakage_guard": "subject calibration subset is disjoint from subject evaluation subset",
        },
        "variants": [
            {
                "variant_name": result.variant_name,
                "model_family": result.model_family,
                "classifier_kind": result.classifier_kind,
                "modality_group": result.modality_group,
                "input_modalities": result.input_modalities,
                "feature_count": len(result.feature_names),
                "split_summary": result.split_summary,
            }
            for result in variant_results
        ],
        "comparison_summary": {
            "winner_by_track": winners,
            "model_comparison": comparison_rows,
            "budget_sensitivity": budget_rows,
        },
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "evaluation_subset": "wesad unified labels with disjoint subject-level calibration/evaluation split",
            "subjects": len({item.subject_id for item in examples}),
            "sessions": len({item.session_id for item in examples}),
            "segments": len(examples),
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "failed_variants": [
            {
                "variant_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "modality_group": item.modality_group,
                "error_type": item.error_type,
                "error_message": item.error_message,
            }
            for item in failed_variants
        ],
        "generated_at_utc": timestamp.isoformat(),
    }

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_h3_predictions_csv(predictions_path, prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_h3_per_subject_metrics_csv(per_subject_path, per_subject_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_h3_model_comparison_csv(comparison_path, comparison_rows)

    failed_variants_path = output_root / "failed-variants.csv"
    _write_failed_variants_csv(path=failed_variants_path, rows=failed_variants)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_h3_report_markdown(
            report=report,
            comparison_rows=comparison_rows,
            per_subject_rows=per_subject_rows,
            budget_rows=budget_rows,
        ),
        encoding="utf-8",
    )
    _generate_h3_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        per_subject_rows=per_subject_rows,
        budget_rows=budget_rows,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "failed_variants_path": str(failed_variants_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "successful_variant_count": len(variant_results),
        "failed_variant_count": len(failed_variants),
    }


def run_h5_weak_label_label_free_wesad(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
    calibration_segments: int = 2,
    adaptation_weight: int = 5,
) -> dict[str, Any]:
    if calibration_segments < 1:
        raise ValueError("calibration_segments must be >= 1")
    if adaptation_weight < 1:
        raise ValueError("adaptation_weight must be >= 1")

    examples, labels, split_manifest = _load_examples(
        paths=paths,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    variants = [
        VariantSpec(
            variant_name="watch_only_ada_boost",
            model_family="adaboost",
            classifier_kind="ada_boost",
            feature_prefixes=("watch_",),
            input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
            description="Watch-only weak-label/label-free candidate.",
            modality_group="watch_only",
        ),
        VariantSpec(
            variant_name="watch_only_random_forest",
            model_family="random_forest",
            classifier_kind="random_forest",
            feature_prefixes=("watch_",),
            input_modalities=("watch_acc", "watch_bvp", "watch_eda", "watch_temp"),
            description="Watch-only fallback weak-label/label-free candidate.",
            modality_group="watch_only",
        ),
        VariantSpec(
            variant_name="fusion_catboost",
            model_family="catboost_multiclass",
            classifier_kind="catboost",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Fusion weak-label/label-free candidate.",
            modality_group="fusion",
        ),
        VariantSpec(
            variant_name="fusion_gaussian_nb",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=(
                "watch_acc",
                "watch_bvp",
                "watch_eda",
                "watch_temp",
                "chest_acc",
                "chest_ecg",
                "chest_eda",
                "chest_emg",
                "chest_resp",
                "chest_temp",
            ),
            description="Fusion fallback weak-label/label-free candidate.",
            modality_group="fusion",
        ),
    ]

    variant_results: list[H5WeakLabelLabelFreeVariantResult] = []
    failed_variants: list[FailedVariantRun] = []
    for variant in variants:
        try:
            variant_results.append(
                _evaluate_h5_weak_label_label_free_variant(
                    examples=examples,
                    variant=variant,
                    calibration_segments=calibration_segments,
                    adaptation_weight=adaptation_weight,
                )
            )
        except Exception as exc:
            failed_variants.append(
                FailedVariantRun(
                    variant_name=variant.variant_name,
                    model_family=variant.model_family,
                    classifier_kind=variant.classifier_kind,
                    modality_group=variant.modality_group,
                    input_modalities=list(variant.input_modalities),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

    if not variant_results:
        raise RuntimeError("all H5 variants failed")

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"h5-weak-label-label-free-wesad-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = paths.output_dir / dataset_id / dataset_version / "weak-label-label-free-personalization"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    comparison_rows = _build_h5_model_comparison_rows(variant_results)
    prediction_rows = [row for result in variant_results for row in result.prediction_rows]
    per_subject_rows = [row for result in variant_results for row in result.per_subject_rows]
    budget_rows = [row for result in variant_results for row in result.budget_rows]

    winners: dict[str, dict[str, Any]] = {}
    for track in ("activity", "arousal_coarse"):
        label_free_rows = [
            row for row in comparison_rows if row["track"] == track and row["evaluation_mode"] == "label_free"
        ]
        best = max(label_free_rows, key=lambda item: float(item["value"]))
        winners[track] = {
            "variant_name": best["variant_name"],
            "model_family": best["model_family"],
            "classifier_kind": best["classifier_kind"],
            "modality_group": best["modality_group"],
            "value": best["value"],
            "delta_vs_global": best["delta_vs_global"],
            "delta_vs_weak_label": best["delta_vs_weak_label"],
            "claim_status": best["claim_status"],
        }

    report = {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "comparison_goal": "Compare weak-label and label-free personalization variants against global baseline on the same subject-level protocol.",
        "research_hypothesis": "Weak-label and label-free adaptation can recover part of personalization gain with reduced manual label dependence.",
        "status": "baseline",
        "calibration_policy": {
            "calibration_segments_per_subject": calibration_segments,
            "weak_label_method": "subject calibration labels are partially replaced by global predictions (deterministic mix)",
            "label_free_method": "subject adaptation uses pseudo-labels from global model only",
            "adaptation_weight": adaptation_weight,
            "leakage_guard": "subject calibration subset is disjoint from subject evaluation subset",
        },
        "variants": [
            {
                "variant_name": result.variant_name,
                "model_family": result.model_family,
                "classifier_kind": result.classifier_kind,
                "modality_group": result.modality_group,
                "input_modalities": result.input_modalities,
                "feature_count": len(result.feature_names),
                "split_summary": result.split_summary,
            }
            for result in variant_results
        ],
        "comparison_summary": {
            "winner_by_track_label_free": winners,
            "model_comparison": comparison_rows,
            "budget_sensitivity": budget_rows,
        },
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "evaluation_subset": "wesad unified labels with disjoint subject-level calibration/evaluation split",
            "subjects": len({item.subject_id for item in examples}),
            "sessions": len({item.session_id for item in examples}),
            "segments": len(examples),
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "failed_variants": [
            {
                "variant_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "modality_group": item.modality_group,
                "error_type": item.error_type,
                "error_message": item.error_message,
            }
            for item in failed_variants
        ],
        "generated_at_utc": timestamp.isoformat(),
    }

    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    predictions_path = output_root / "predictions-test.csv"
    _write_h5_predictions_csv(predictions_path, prediction_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_h5_per_subject_metrics_csv(per_subject_path, per_subject_rows)

    comparison_path = output_root / "model-comparison.csv"
    _write_h5_model_comparison_csv(comparison_path, comparison_rows)

    failed_variants_path = output_root / "failed-variants.csv"
    _write_failed_variants_csv(path=failed_variants_path, rows=failed_variants)

    report_md_path = output_root / "research-report.md"
    report_md_path.write_text(
        _build_h5_report_markdown(
            report=report,
            comparison_rows=comparison_rows,
            per_subject_rows=per_subject_rows,
            budget_rows=budget_rows,
        ),
        encoding="utf-8",
    )
    _generate_h5_plots(
        plots_dir=plots_dir,
        comparison_rows=comparison_rows,
        per_subject_rows=per_subject_rows,
        budget_rows=budget_rows,
    )

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "predictions_path": str(predictions_path),
        "per_subject_metrics_path": str(per_subject_path),
        "model_comparison_path": str(comparison_path),
        "failed_variants_path": str(failed_variants_path),
        "research_report_path": str(report_md_path),
        "plots_dir": str(plots_dir),
        "successful_variant_count": len(variant_results),
        "failed_variant_count": len(failed_variants),
    }


def run_g3_wesad_comparative_report(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    del min_confidence  # G3 aggregates already materialized G1/G2 outputs.
    root = paths.output_dir / dataset_id / dataset_version
    g1_report_path = root / "watch-only-baseline" / "evaluation-report.json"
    g2_report_path = root / "fusion-baseline" / "evaluation-report.json"
    g2_per_subject_path = root / "fusion-baseline" / "per-subject-metrics.csv"
    if not g1_report_path.exists():
        raise FileNotFoundError(f"missing G1 report: {g1_report_path}")
    if not g2_report_path.exists():
        raise FileNotFoundError(f"missing G2 report: {g2_report_path}")
    if not g2_per_subject_path.exists():
        raise FileNotFoundError(f"missing G2 per-subject metrics: {g2_per_subject_path}")

    g1_report = _load_json(g1_report_path)
    g2_report = _load_json(g2_report_path)
    g2_rows = g2_report["comparison_summary"]["model_comparison"]

    g1_rows = _g1_comparison_rows(g1_report)
    comparison_rows = g1_rows + [dict(row) for row in g2_rows]
    for row in comparison_rows:
        if row["variant_name"].startswith("g1_"):
            row["source_step"] = "G1"
            row["run_id"] = g1_report["experiment_id"]
        else:
            row["source_step"] = "G2"
            row["run_id"] = g2_report["experiment_id"]

    per_subject_rows = _g1_per_subject_rows(g1_report) + _load_csv_dict_rows(g2_per_subject_path)
    for row in per_subject_rows:
        if row["variant_name"].startswith("g1_"):
            row["source_step"] = "G1"
            row["run_id"] = g1_report["experiment_id"]
        else:
            row["source_step"] = "G2"
            row["run_id"] = g2_report["experiment_id"]

    winners = {}
    for track_name in ("activity", "arousal_coarse"):
        track_rows = [row for row in comparison_rows if row["track"] == track_name]
        winner = max(track_rows, key=lambda item: float(item["value"]))
        winners[track_name] = {
            "variant_name": winner["variant_name"],
            "value": float(winner["value"]),
            "claim_status": winner["claim_status"],
            "source_step": winner["source_step"],
        }

    timestamp = datetime.now(timezone.utc)
    experiment_id = f"g3-comparison-wesad-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"
    output_root = root / "comparison"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "comparison_scope": "Aggregate and compare G1 + G2 baseline runs under the same WESAD subject-wise split.",
        "source_runs": [
            {"step": "G1", "experiment_id": g1_report["experiment_id"], "report_path": str(g1_report_path)},
            {"step": "G2", "experiment_id": g2_report["experiment_id"], "report_path": str(g2_report_path)},
        ],
        "winner_by_track": winners,
        "model_comparison": comparison_rows,
        "generated_at_utc": timestamp.isoformat(),
    }
    report_path = output_root / "evaluation-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    model_comparison_path = output_root / "model-comparison.csv"
    _write_g3_model_comparison_csv(model_comparison_path, comparison_rows)

    per_subject_path = output_root / "per-subject-metrics.csv"
    _write_g3_per_subject_csv(per_subject_path, per_subject_rows)

    comparison_report_path = output_root / "comparison-report.md"
    comparison_report_path.write_text(
        _build_g3_report_markdown(report=report, g1_report=g1_report, g2_report=g2_report),
        encoding="utf-8",
    )
    research_report_path = output_root / "research-report.md"
    research_report_path.write_text(comparison_report_path.read_text(encoding="utf-8"), encoding="utf-8")

    _generate_g3_plots(plots_dir=plots_dir, comparison_rows=comparison_rows, per_subject_rows=per_subject_rows)

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "comparison_report_path": str(comparison_report_path),
        "research_report_path": str(research_report_path),
        "model_comparison_path": str(model_comparison_path),
        "per_subject_metrics_path": str(per_subject_path),
        "plots_dir": str(plots_dir),
        "run_count": len({row["variant_name"] for row in comparison_rows}),
    }


class CentroidClassifier:
    def __init__(self) -> None:
        self._labels: list[str] = []
        self._centroids: np.ndarray | None = None
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None

    def fit(self, features: np.ndarray, labels: list[str]) -> None:
        if features.shape[0] == 0:
            raise ValueError("cannot fit classifier on empty features")
        if features.shape[0] != len(labels):
            raise ValueError("features row count must match labels count")

        mean = features.mean(axis=0)
        std = features.std(axis=0)
        std = np.where(std == 0.0, 1.0, std)
        normalized = (features - mean) / std

        ordered_labels = sorted(set(labels))
        centroids = []
        for label in ordered_labels:
            mask = np.asarray([item == label for item in labels], dtype=bool)
            centroids.append(normalized[mask].mean(axis=0))

        self._labels = ordered_labels
        self._centroids = np.asarray(centroids, dtype=float)
        self._mean = mean
        self._std = std

    def predict(self, features: np.ndarray) -> list[str]:
        if self._centroids is None or self._mean is None or self._std is None:
            raise ValueError("classifier is not fitted")
        if features.shape[0] == 0:
            return []

        normalized = (features - self._mean) / self._std
        distances = np.linalg.norm(normalized[:, np.newaxis, :] - self._centroids[np.newaxis, :, :], axis=2)
        nearest = distances.argmin(axis=1)
        return [self._labels[i] for i in nearest.tolist()]

    def feature_importance_rows(
        self,
        variant_name: str,
        track: str,
        feature_names: list[str],
    ) -> list[dict[str, Any]]:
        del variant_name, track, feature_names
        return []


class GaussianNBClassifier:
    def __init__(self, var_smoothing: float = 1e-9) -> None:
        self._labels: list[str] = []
        self._means: np.ndarray | None = None
        self._variances: np.ndarray | None = None
        self._log_priors: np.ndarray | None = None
        self._var_smoothing = var_smoothing

    def fit(self, features: np.ndarray, labels: list[str]) -> None:
        if features.shape[0] == 0:
            raise ValueError("cannot fit classifier on empty features")
        if features.shape[0] != len(labels):
            raise ValueError("features row count must match labels count")

        ordered_labels = sorted(set(labels))
        means = []
        variances = []
        priors = []
        for label in ordered_labels:
            mask = np.asarray([item == label for item in labels], dtype=bool)
            subset = features[mask]
            means.append(subset.mean(axis=0))
            variances.append(subset.var(axis=0) + self._var_smoothing)
            priors.append(subset.shape[0] / features.shape[0])

        self._labels = ordered_labels
        self._means = np.asarray(means, dtype=float)
        self._variances = np.asarray(variances, dtype=float)
        self._log_priors = np.log(np.asarray(priors, dtype=float))

    def predict(self, features: np.ndarray) -> list[str]:
        if self._means is None or self._variances is None or self._log_priors is None:
            raise ValueError("classifier is not fitted")
        if features.shape[0] == 0:
            return []

        all_scores = []
        for row in features:
            log_probs = []
            for index, _ in enumerate(self._labels):
                mean = self._means[index]
                variance = self._variances[index]
                log_likelihood = -0.5 * np.sum(np.log(2.0 * math.pi * variance) + ((row - mean) ** 2) / variance)
                log_probs.append(float(self._log_priors[index] + log_likelihood))
            all_scores.append(log_probs)
        best = np.asarray(all_scores, dtype=float).argmax(axis=1)
        return [self._labels[i] for i in best.tolist()]

    def feature_importance_rows(
        self,
        variant_name: str,
        track: str,
        feature_names: list[str],
    ) -> list[dict[str, Any]]:
        del variant_name, track, feature_names
        return []


def _load_examples(
    paths: PipelinePaths,
    dataset_id: str,
    dataset_version: str,
    min_confidence: float,
) -> tuple[list[SegmentExample], list[dict[str, Any]], dict[str, Any]]:
    labels = _load_jsonl(paths.segment_labels_path)
    split_manifest = _load_json(paths.split_manifest_path)
    split_index = _split_subject_index(split_manifest=split_manifest)
    examples = _build_examples(
        labels=labels,
        split_index=split_index,
        raw_root=paths.raw_wesad_root,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
    )
    if not examples:
        raise ValueError("no usable segment examples found")
    return examples, labels, split_manifest


def _evaluate_variant(
    examples: list[SegmentExample],
    variant: VariantSpec,
    model_save_dir: Path | None = None,
) -> VariantRunResult:
    all_feature_names = sorted(examples[0].features.keys())
    feature_names = _select_feature_names(all_feature_names, variant.feature_prefixes)
    if not feature_names:
        raise ValueError(f"variant {variant.variant_name} has no feature set")

    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    test_examples = [item for item in examples if item.split == "test"]
    if not train_examples or not test_examples:
        raise ValueError("insufficient split coverage: train and test must be non-empty")

    x_train = _to_feature_matrix(train_examples, feature_names)
    x_validation = _to_feature_matrix(validation_examples, feature_names)
    x_test = _to_feature_matrix(test_examples, feature_names)

    activity_train = [item.activity_label for item in train_examples]
    activity_validation = [item.activity_label for item in validation_examples]
    activity_test = [item.activity_label for item in test_examples]

    arousal_train_scores = [item.arousal_score for item in train_examples]
    arousal_validation_scores = [item.arousal_score for item in validation_examples]
    arousal_test_scores = [item.arousal_score for item in test_examples]
    arousal_train = [item.arousal_coarse for item in train_examples]
    arousal_validation = [item.arousal_coarse for item in validation_examples]
    arousal_test = [item.arousal_coarse for item in test_examples]

    activity_model = _build_classifier(variant.classifier_kind)
    activity_model.fit(x_train, activity_train)
    activity_validation_pred = activity_model.predict(x_validation)
    activity_test_pred = activity_model.predict(x_test)

    arousal_model = _build_classifier(variant.classifier_kind)
    arousal_model.fit(x_train, arousal_train)
    arousal_validation_pred = arousal_model.predict(x_validation)
    arousal_test_pred = arousal_model.predict(x_test)

    coarse_to_score = _coarse_class_score_mapping(arousal_train_scores, arousal_train)
    arousal_test_score_pred = [coarse_to_score.get(label, 5) for label in arousal_test_pred]

    majority_activity = _majority_label(activity_train)
    majority_arousal = _majority_label(arousal_train)
    median_arousal = int(round(float(np.median(np.asarray(arousal_train_scores, dtype=float)))))

    activity_test_metrics = compute_classification_metrics(activity_test, activity_test_pred)
    activity_test_majority_metrics = compute_classification_metrics(activity_test, [majority_activity] * len(activity_test))
    arousal_test_metrics = compute_classification_metrics(arousal_test, arousal_test_pred)
    arousal_test_majority_metrics = compute_classification_metrics(arousal_test, [majority_arousal] * len(arousal_test))

    arousal_test_ordinal = {
        "mae": compute_mae(arousal_test_scores, arousal_test_score_pred),
        "spearman_rho": compute_spearman_rho(arousal_test_scores, arousal_test_score_pred),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            arousal_test_scores,
            arousal_test_score_pred,
            min_rating=1,
            max_rating=9,
        ),
    }
    arousal_test_ordinal_median = {
        "mae": compute_mae(arousal_test_scores, [median_arousal] * len(arousal_test_scores)),
        "spearman_rho": compute_spearman_rho(arousal_test_scores, [median_arousal] * len(arousal_test_scores)),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            arousal_test_scores,
            [median_arousal] * len(arousal_test_scores),
            min_rating=1,
            max_rating=9,
        ),
    }

    subject_breakdown_activity = _subject_breakdown(
        examples=test_examples,
        predicted=activity_test_pred,
        target_field="activity_label",
    )
    subject_breakdown_arousal = _subject_breakdown(
        examples=test_examples,
        predicted=arousal_test_pred,
        target_field="arousal_coarse",
    )
    activity_ci = _bootstrap_primary_metric_ci(
        examples=test_examples,
        predicted=activity_test_pred,
        baseline=[majority_activity] * len(activity_test),
        target_field="activity_label",
    )
    arousal_ci = _bootstrap_primary_metric_ci(
        examples=test_examples,
        predicted=arousal_test_pred,
        baseline=[majority_arousal] * len(arousal_test),
        target_field="arousal_coarse",
    )

    tracks = {
        "activity": _classification_block(
            test_metrics=activity_test_metrics,
            majority_metrics=activity_test_majority_metrics,
            validation_target=activity_validation,
            validation_predicted=activity_validation_pred,
            test_target=activity_test,
            test_predicted=activity_test_pred,
            subject_breakdown=subject_breakdown_activity,
            ci=activity_ci,
        ),
        "arousal_coarse": _classification_block(
            test_metrics=arousal_test_metrics,
            majority_metrics=arousal_test_majority_metrics,
            validation_target=arousal_validation,
            validation_predicted=arousal_validation_pred,
            test_target=arousal_test,
            test_predicted=arousal_test_pred,
            subject_breakdown=subject_breakdown_arousal,
            ci=arousal_ci,
        ),
        "arousal_ordinal": {
            "test": arousal_test_ordinal,
            "global_median_predictor_test": arousal_test_ordinal_median,
        },
    }
    per_subject_rows = _per_subject_metric_rows(variant.variant_name, subject_breakdown_activity, subject_breakdown_arousal)
    feature_importance_rows = activity_model.feature_importance_rows(
        variant_name=variant.variant_name,
        track="activity",
        feature_names=feature_names,
    ) + arousal_model.feature_importance_rows(
        variant_name=variant.variant_name,
        track="arousal_coarse",
        feature_names=feature_names,
    )

    if model_save_dir is not None:
        model_save_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(activity_model, model_save_dir / f"{variant.variant_name}_activity.joblib")
        joblib.dump(arousal_model, model_save_dir / f"{variant.variant_name}_arousal.joblib")
        (model_save_dir / "feature_names.json").write_text(
            json.dumps({"feature_names": feature_names}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return VariantRunResult(
        variant_name=variant.variant_name,
        model_family=variant.model_family,
        classifier_kind=variant.classifier_kind,
        modality_group=variant.modality_group,
        input_modalities=list(variant.input_modalities),
        feature_names=feature_names,
        activity_validation_pred=activity_validation_pred,
        activity_test_pred=activity_test_pred,
        arousal_validation_pred=arousal_validation_pred,
        arousal_test_pred=arousal_test_pred,
        arousal_test_score_pred=arousal_test_score_pred,
        tracks=tracks,
        splits={
            "train": _split_summary(train_examples),
            "validation": _split_summary(validation_examples),
            "test": _split_summary(test_examples),
        },
        per_subject_rows=per_subject_rows,
        feature_importance_rows=feature_importance_rows,
    )


def _build_classifier(kind: str) -> Any:
    if kind == "centroid":
        return CentroidClassifier()
    if kind == "gaussian_nb":
        return GaussianNBClassifier()
    if kind in supported_classifier_kinds():
        return build_estimator_classifier(kind)
    raise ValueError(f"unsupported classifier kind: {kind}")


def _evaluate_variant_for_e2_3(
    examples: list[SegmentExample],
    variant: VariantSpec,
) -> dict[str, Any]:
    all_feature_names = sorted(examples[0].features.keys())
    feature_names = _select_feature_names(all_feature_names, variant.feature_prefixes)
    if not feature_names:
        raise ValueError(f"variant {variant.variant_name} has no feature set")

    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    test_examples = [item for item in examples if item.split == "test"]
    if not train_examples or not test_examples:
        raise ValueError("insufficient split coverage: train and test must be non-empty")

    x_train = _to_feature_matrix(train_examples, feature_names)
    x_validation = _to_feature_matrix(validation_examples, feature_names)
    x_test = _to_feature_matrix(test_examples, feature_names)

    arousal_train_scores = [item.arousal_score for item in train_examples]
    arousal_validation_scores = [item.arousal_score for item in validation_examples]
    arousal_test_scores = [item.arousal_score for item in test_examples]
    arousal_train = [item.arousal_coarse for item in train_examples]
    arousal_validation = [item.arousal_coarse for item in validation_examples]
    arousal_test = [item.arousal_coarse for item in test_examples]

    valence_train_scores = [item.valence_score for item in train_examples]
    valence_validation_scores = [item.valence_score for item in validation_examples]
    valence_test_scores = [item.valence_score for item in test_examples]
    valence_train = [item.valence_coarse for item in train_examples]
    valence_validation = [item.valence_coarse for item in validation_examples]
    valence_test = [item.valence_coarse for item in test_examples]

    arousal_model = _build_classifier(variant.classifier_kind)
    arousal_model.fit(x_train, arousal_train)
    arousal_validation_pred = arousal_model.predict(x_validation)
    arousal_test_pred = arousal_model.predict(x_test)

    valence_model = _build_classifier(variant.classifier_kind)
    valence_model.fit(x_train, valence_train)
    valence_validation_pred = valence_model.predict(x_validation)
    valence_test_pred = valence_model.predict(x_test)

    arousal_coarse_to_score = _coarse_class_score_mapping(arousal_train_scores, arousal_train)
    arousal_test_score_pred = [arousal_coarse_to_score.get(label, 5) for label in arousal_test_pred]
    valence_coarse_to_score = _coarse_class_score_mapping(valence_train_scores, valence_train)
    valence_test_score_pred = [valence_coarse_to_score.get(label, 5) for label in valence_test_pred]

    arousal_majority = _majority_label(arousal_train)
    valence_majority = _majority_label(valence_train)
    arousal_median = int(round(float(np.median(np.asarray(arousal_train_scores, dtype=float)))))
    valence_median = int(round(float(np.median(np.asarray(valence_train_scores, dtype=float)))))

    arousal_test_metrics = compute_classification_metrics(arousal_test, arousal_test_pred)
    arousal_test_majority_metrics = compute_classification_metrics(arousal_test, [arousal_majority] * len(arousal_test))
    valence_test_metrics = compute_classification_metrics(valence_test, valence_test_pred)
    valence_test_majority_metrics = compute_classification_metrics(valence_test, [valence_majority] * len(valence_test))

    arousal_test_ordinal = {
        "mae": compute_mae(arousal_test_scores, arousal_test_score_pred),
        "spearman_rho": compute_spearman_rho(arousal_test_scores, arousal_test_score_pred),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            arousal_test_scores,
            arousal_test_score_pred,
            min_rating=1,
            max_rating=9,
        ),
    }
    arousal_test_ordinal_median = {
        "mae": compute_mae(arousal_test_scores, [arousal_median] * len(arousal_test_scores)),
        "spearman_rho": compute_spearman_rho(arousal_test_scores, [arousal_median] * len(arousal_test_scores)),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            arousal_test_scores,
            [arousal_median] * len(arousal_test_scores),
            min_rating=1,
            max_rating=9,
        ),
    }
    valence_test_ordinal = {
        "mae": compute_mae(valence_test_scores, valence_test_score_pred),
        "spearman_rho": compute_spearman_rho(valence_test_scores, valence_test_score_pred),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            valence_test_scores,
            valence_test_score_pred,
            min_rating=1,
            max_rating=9,
        ),
    }
    valence_test_ordinal_median = {
        "mae": compute_mae(valence_test_scores, [valence_median] * len(valence_test_scores)),
        "spearman_rho": compute_spearman_rho(valence_test_scores, [valence_median] * len(valence_test_scores)),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            valence_test_scores,
            [valence_median] * len(valence_test_scores),
            min_rating=1,
            max_rating=9,
        ),
    }

    subject_breakdown_arousal = _subject_breakdown(
        examples=test_examples,
        predicted=arousal_test_pred,
        target_field="arousal_coarse",
    )
    subject_breakdown_valence = _subject_breakdown(
        examples=test_examples,
        predicted=valence_test_pred,
        target_field="valence_coarse",
    )
    arousal_ci = _bootstrap_primary_metric_ci(
        examples=test_examples,
        predicted=arousal_test_pred,
        baseline=[arousal_majority] * len(arousal_test),
        target_field="arousal_coarse",
    )
    valence_ci = _bootstrap_primary_metric_ci(
        examples=test_examples,
        predicted=valence_test_pred,
        baseline=[valence_majority] * len(valence_test),
        target_field="valence_coarse",
    )

    tracks = {
        "arousal_coarse": _classification_block(
            test_metrics=arousal_test_metrics,
            majority_metrics=arousal_test_majority_metrics,
            validation_target=arousal_validation,
            validation_predicted=arousal_validation_pred,
            test_target=arousal_test,
            test_predicted=arousal_test_pred,
            subject_breakdown=subject_breakdown_arousal,
            ci=arousal_ci,
        ),
        "arousal_ordinal": {
            "test": arousal_test_ordinal,
            "global_median_predictor_test": arousal_test_ordinal_median,
        },
        "valence_coarse": _classification_block(
            test_metrics=valence_test_metrics,
            majority_metrics=valence_test_majority_metrics,
            validation_target=valence_validation,
            validation_predicted=valence_validation_pred,
            test_target=valence_test,
            test_predicted=valence_test_pred,
            subject_breakdown=subject_breakdown_valence,
            ci=valence_ci,
        ),
        "valence_ordinal": {
            "test": valence_test_ordinal,
            "global_median_predictor_test": valence_test_ordinal_median,
        },
    }

    per_subject_rows = _per_subject_rows_for_tracks(
        variant_name=variant.variant_name,
        track_rows={
            "arousal_coarse": subject_breakdown_arousal,
            "valence_coarse": subject_breakdown_valence,
        },
    )
    prediction_rows = _prediction_rows_e2_3(
        variant_name=variant.variant_name,
        model_family=variant.model_family,
        examples=test_examples,
        arousal_pred=arousal_test_pred,
        arousal_score_pred=arousal_test_score_pred,
        valence_pred=valence_test_pred,
        valence_score_pred=valence_test_score_pred,
    )

    return {
        "variant_name": variant.variant_name,
        "model_family": variant.model_family,
        "classifier_kind": variant.classifier_kind,
        "modality_group": variant.modality_group,
        "input_modalities": list(variant.input_modalities),
        "feature_names": feature_names,
        "tracks": tracks,
        "per_subject_rows": per_subject_rows,
        "prediction_rows": prediction_rows,
        "arousal_test_pred": arousal_test_pred,
        "valence_test_pred": valence_test_pred,
    }


def _evaluate_light_personalization_variant(
    examples: list[SegmentExample],
    variant: VariantSpec,
    calibration_segments: int,
) -> LightPersonalizationVariantResult:
    all_feature_names = sorted(examples[0].features.keys())
    feature_names = _select_feature_names(all_feature_names, variant.feature_prefixes)
    if not feature_names:
        raise ValueError(f"variant {variant.variant_name} has no feature set")

    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    global_train_examples = train_examples + validation_examples
    test_examples = [item for item in examples if item.split == "test"]
    if not global_train_examples or not test_examples:
        raise ValueError("insufficient split coverage for H2")

    x_train = _to_feature_matrix(global_train_examples, feature_names)
    activity_train = [item.activity_label for item in global_train_examples]
    arousal_train = [item.arousal_coarse for item in global_train_examples]
    arousal_train_scores = [item.arousal_score for item in global_train_examples]
    coarse_to_score = _coarse_class_score_mapping(arousal_train_scores, arousal_train)

    activity_model = _build_classifier(variant.classifier_kind)
    activity_model.fit(x_train, activity_train)
    arousal_model = _build_classifier(variant.classifier_kind)
    arousal_model.fit(x_train, arousal_train)

    prediction_payload = _subject_calibration_predictions(
        subject_examples=test_examples,
        feature_names=feature_names,
        activity_model=activity_model,
        arousal_model=arousal_model,
        coarse_to_score=coarse_to_score,
        calibration_segments=calibration_segments,
    )
    if not prediction_payload["eval_examples"]:
        raise ValueError("no evaluation examples after calibration split")
    for row in prediction_payload["per_subject_rows"]:
        row["variant_name"] = variant.variant_name

    eval_examples = prediction_payload["eval_examples"]
    global_activity_pred = prediction_payload["global_activity_pred"]
    personalized_activity_pred = prediction_payload["personalized_activity_pred"]
    global_arousal_pred = prediction_payload["global_arousal_pred"]
    personalized_arousal_pred = prediction_payload["personalized_arousal_pred"]

    truth_activity = [item.activity_label for item in eval_examples]
    truth_arousal = [item.arousal_coarse for item in eval_examples]
    global_activity_metrics = compute_classification_metrics(truth_activity, global_activity_pred)
    personalized_activity_metrics = compute_classification_metrics(truth_activity, personalized_activity_pred)
    global_arousal_metrics = compute_classification_metrics(truth_arousal, global_arousal_pred)
    personalized_arousal_metrics = compute_classification_metrics(truth_arousal, personalized_arousal_pred)

    prediction_rows = _h2_prediction_rows(
        variant=variant,
        examples=eval_examples,
        global_activity_pred=global_activity_pred,
        personalized_activity_pred=personalized_activity_pred,
        global_arousal_pred=global_arousal_pred,
        personalized_arousal_pred=personalized_arousal_pred,
        coarse_to_score=coarse_to_score,
        subject_calibration_examples=prediction_payload["calibration_examples_by_subject"],
    )
    budget_rows: list[dict[str, Any]] = []
    for budget in sorted({1, calibration_segments, 2, 3, 4}):
        if budget < 1:
            continue
        budget_payload = _subject_calibration_predictions(
            subject_examples=test_examples,
            feature_names=feature_names,
            activity_model=activity_model,
            arousal_model=arousal_model,
            coarse_to_score=coarse_to_score,
            calibration_segments=budget,
        )
        if not budget_payload["eval_examples"]:
            continue
        budget_examples = budget_payload["eval_examples"]
        budget_truth_activity = [item.activity_label for item in budget_examples]
        budget_truth_arousal = [item.arousal_coarse for item in budget_examples]
        budget_global_activity = compute_classification_metrics(
            budget_truth_activity,
            budget_payload["global_activity_pred"],
        ).macro_f1
        budget_personalized_activity = compute_classification_metrics(
            budget_truth_activity,
            budget_payload["personalized_activity_pred"],
        ).macro_f1
        budget_global_arousal = compute_classification_metrics(
            budget_truth_arousal,
            budget_payload["global_arousal_pred"],
        ).macro_f1
        budget_personalized_arousal = compute_classification_metrics(
            budget_truth_arousal,
            budget_payload["personalized_arousal_pred"],
        ).macro_f1
        budget_rows.extend(
            [
                {
                    "variant_name": variant.variant_name,
                    "track": "activity",
                    "calibration_segments": budget,
                    "global_macro_f1": round(budget_global_activity, 6),
                    "personalized_macro_f1": round(budget_personalized_activity, 6),
                    "gain": round(budget_personalized_activity - budget_global_activity, 6),
                    "eval_subjects": len({item.subject_id for item in budget_examples}),
                    "eval_segments": len(budget_examples),
                },
                {
                    "variant_name": variant.variant_name,
                    "track": "arousal_coarse",
                    "calibration_segments": budget,
                    "global_macro_f1": round(budget_global_arousal, 6),
                    "personalized_macro_f1": round(budget_personalized_arousal, 6),
                    "gain": round(budget_personalized_arousal - budget_global_arousal, 6),
                    "eval_subjects": len({item.subject_id for item in budget_examples}),
                    "eval_segments": len(budget_examples),
                },
            ]
        )

    return LightPersonalizationVariantResult(
        variant_name=variant.variant_name,
        model_family=variant.model_family,
        classifier_kind=variant.classifier_kind,
        modality_group=variant.modality_group,
        input_modalities=list(variant.input_modalities),
        feature_names=feature_names,
        calibration_segments=calibration_segments,
        global_metrics={
            "activity": global_activity_metrics,
            "arousal_coarse": global_arousal_metrics,
        },
        personalized_metrics={
            "activity": personalized_activity_metrics,
            "arousal_coarse": personalized_arousal_metrics,
        },
        per_subject_rows=prediction_payload["per_subject_rows"],
        prediction_rows=prediction_rows,
        budget_rows=budget_rows,
        split_summary={
            "global_train_subjects": len({item.subject_id for item in global_train_examples}),
            "global_train_segments": len(global_train_examples),
            "test_subjects": len({item.subject_id for item in test_examples}),
            "test_segments": len(test_examples),
            "eval_subjects_after_calibration": len({item.subject_id for item in eval_examples}),
            "eval_segments_after_calibration": len(eval_examples),
        },
    )


def _evaluate_full_personalization_variant(
    examples: list[SegmentExample],
    variant: VariantSpec,
    calibration_segments: int,
    adaptation_weight: int,
) -> FullPersonalizationVariantResult:
    all_feature_names = sorted(examples[0].features.keys())
    feature_names = _select_feature_names(all_feature_names, variant.feature_prefixes)
    if not feature_names:
        raise ValueError(f"variant {variant.variant_name} has no feature set")

    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    global_train_examples = train_examples + validation_examples
    test_examples = [item for item in examples if item.split == "test"]
    if not global_train_examples or not test_examples:
        raise ValueError("insufficient split coverage for H3")

    x_train = _to_feature_matrix(global_train_examples, feature_names)
    activity_train = [item.activity_label for item in global_train_examples]
    arousal_train = [item.arousal_coarse for item in global_train_examples]
    arousal_train_scores = [item.arousal_score for item in global_train_examples]
    coarse_to_score = _coarse_class_score_mapping(arousal_train_scores, arousal_train)

    activity_model = _build_classifier(variant.classifier_kind)
    activity_model.fit(x_train, activity_train)
    arousal_model = _build_classifier(variant.classifier_kind)
    arousal_model.fit(x_train, arousal_train)

    prediction_payload = _subject_full_personalization_predictions(
        global_train_examples=global_train_examples,
        subject_examples=test_examples,
        feature_names=feature_names,
        classifier_kind=variant.classifier_kind,
        global_activity_model=activity_model,
        global_arousal_model=arousal_model,
        coarse_to_score=coarse_to_score,
        calibration_segments=calibration_segments,
        adaptation_weight=adaptation_weight,
    )
    if not prediction_payload["eval_examples"]:
        raise ValueError("no evaluation examples after calibration split")
    for row in prediction_payload["per_subject_rows"]:
        row["variant_name"] = variant.variant_name

    eval_examples = prediction_payload["eval_examples"]
    truth_activity = [item.activity_label for item in eval_examples]
    truth_arousal = [item.arousal_coarse for item in eval_examples]

    global_activity_metrics = compute_classification_metrics(truth_activity, prediction_payload["global_activity_pred"])
    light_activity_metrics = compute_classification_metrics(truth_activity, prediction_payload["light_activity_pred"])
    full_activity_metrics = compute_classification_metrics(truth_activity, prediction_payload["full_activity_pred"])
    global_arousal_metrics = compute_classification_metrics(truth_arousal, prediction_payload["global_arousal_pred"])
    light_arousal_metrics = compute_classification_metrics(truth_arousal, prediction_payload["light_arousal_pred"])
    full_arousal_metrics = compute_classification_metrics(truth_arousal, prediction_payload["full_arousal_pred"])

    prediction_rows = _h3_prediction_rows(
        variant=variant,
        examples=eval_examples,
        global_activity_pred=prediction_payload["global_activity_pred"],
        light_activity_pred=prediction_payload["light_activity_pred"],
        full_activity_pred=prediction_payload["full_activity_pred"],
        global_arousal_pred=prediction_payload["global_arousal_pred"],
        light_arousal_pred=prediction_payload["light_arousal_pred"],
        full_arousal_pred=prediction_payload["full_arousal_pred"],
        coarse_to_score=coarse_to_score,
    )

    budget_rows: list[dict[str, Any]] = []
    for budget in sorted({1, calibration_segments, 2, 3, 4}):
        if budget < 1:
            continue
        budget_payload = _subject_full_personalization_predictions(
            global_train_examples=global_train_examples,
            subject_examples=test_examples,
            feature_names=feature_names,
            classifier_kind=variant.classifier_kind,
            global_activity_model=activity_model,
            global_arousal_model=arousal_model,
            coarse_to_score=coarse_to_score,
            calibration_segments=budget,
            adaptation_weight=adaptation_weight,
        )
        if not budget_payload["eval_examples"]:
            continue
        budget_examples = budget_payload["eval_examples"]
        budget_truth_activity = [item.activity_label for item in budget_examples]
        budget_truth_arousal = [item.arousal_coarse for item in budget_examples]
        budget_rows.extend(
            [
                {
                    "variant_name": variant.variant_name,
                    "track": "activity",
                    "calibration_segments": budget,
                    "global_macro_f1": round(
                        compute_classification_metrics(budget_truth_activity, budget_payload["global_activity_pred"]).macro_f1,
                        6,
                    ),
                    "light_macro_f1": round(
                        compute_classification_metrics(budget_truth_activity, budget_payload["light_activity_pred"]).macro_f1,
                        6,
                    ),
                    "full_macro_f1": round(
                        compute_classification_metrics(budget_truth_activity, budget_payload["full_activity_pred"]).macro_f1,
                        6,
                    ),
                    "gain_light_vs_global": round(
                        compute_classification_metrics(budget_truth_activity, budget_payload["light_activity_pred"]).macro_f1
                        - compute_classification_metrics(budget_truth_activity, budget_payload["global_activity_pred"]).macro_f1,
                        6,
                    ),
                    "gain_full_vs_global": round(
                        compute_classification_metrics(budget_truth_activity, budget_payload["full_activity_pred"]).macro_f1
                        - compute_classification_metrics(budget_truth_activity, budget_payload["global_activity_pred"]).macro_f1,
                        6,
                    ),
                    "gain_full_vs_light": round(
                        compute_classification_metrics(budget_truth_activity, budget_payload["full_activity_pred"]).macro_f1
                        - compute_classification_metrics(budget_truth_activity, budget_payload["light_activity_pred"]).macro_f1,
                        6,
                    ),
                    "eval_subjects": len({item.subject_id for item in budget_examples}),
                    "eval_segments": len(budget_examples),
                },
                {
                    "variant_name": variant.variant_name,
                    "track": "arousal_coarse",
                    "calibration_segments": budget,
                    "global_macro_f1": round(
                        compute_classification_metrics(budget_truth_arousal, budget_payload["global_arousal_pred"]).macro_f1,
                        6,
                    ),
                    "light_macro_f1": round(
                        compute_classification_metrics(budget_truth_arousal, budget_payload["light_arousal_pred"]).macro_f1,
                        6,
                    ),
                    "full_macro_f1": round(
                        compute_classification_metrics(budget_truth_arousal, budget_payload["full_arousal_pred"]).macro_f1,
                        6,
                    ),
                    "gain_light_vs_global": round(
                        compute_classification_metrics(budget_truth_arousal, budget_payload["light_arousal_pred"]).macro_f1
                        - compute_classification_metrics(budget_truth_arousal, budget_payload["global_arousal_pred"]).macro_f1,
                        6,
                    ),
                    "gain_full_vs_global": round(
                        compute_classification_metrics(budget_truth_arousal, budget_payload["full_arousal_pred"]).macro_f1
                        - compute_classification_metrics(budget_truth_arousal, budget_payload["global_arousal_pred"]).macro_f1,
                        6,
                    ),
                    "gain_full_vs_light": round(
                        compute_classification_metrics(budget_truth_arousal, budget_payload["full_arousal_pred"]).macro_f1
                        - compute_classification_metrics(budget_truth_arousal, budget_payload["light_arousal_pred"]).macro_f1,
                        6,
                    ),
                    "eval_subjects": len({item.subject_id for item in budget_examples}),
                    "eval_segments": len(budget_examples),
                },
            ]
        )

    return FullPersonalizationVariantResult(
        variant_name=variant.variant_name,
        model_family=variant.model_family,
        classifier_kind=variant.classifier_kind,
        modality_group=variant.modality_group,
        input_modalities=list(variant.input_modalities),
        feature_names=feature_names,
        calibration_segments=calibration_segments,
        adaptation_weight=adaptation_weight,
        global_metrics={"activity": global_activity_metrics, "arousal_coarse": global_arousal_metrics},
        light_metrics={"activity": light_activity_metrics, "arousal_coarse": light_arousal_metrics},
        full_metrics={"activity": full_activity_metrics, "arousal_coarse": full_arousal_metrics},
        per_subject_rows=prediction_payload["per_subject_rows"],
        prediction_rows=prediction_rows,
        budget_rows=budget_rows,
        split_summary={
            "global_train_subjects": len({item.subject_id for item in global_train_examples}),
            "global_train_segments": len(global_train_examples),
            "test_subjects": len({item.subject_id for item in test_examples}),
            "test_segments": len(test_examples),
            "eval_subjects_after_calibration": len({item.subject_id for item in eval_examples}),
            "eval_segments_after_calibration": len(eval_examples),
        },
    )


def _evaluate_h5_weak_label_label_free_variant(
    examples: list[SegmentExample],
    variant: VariantSpec,
    calibration_segments: int,
    adaptation_weight: int,
) -> H5WeakLabelLabelFreeVariantResult:
    all_feature_names = sorted(examples[0].features.keys())
    feature_names = _select_feature_names(all_feature_names, variant.feature_prefixes)
    if not feature_names:
        raise ValueError(f"variant {variant.variant_name} has no feature set")

    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    global_train_examples = train_examples + validation_examples
    test_examples = [item for item in examples if item.split == "test"]
    if not global_train_examples or not test_examples:
        raise ValueError("insufficient split coverage for H5")

    x_train = _to_feature_matrix(global_train_examples, feature_names)
    activity_train = [item.activity_label for item in global_train_examples]
    arousal_train = [item.arousal_coarse for item in global_train_examples]
    arousal_train_scores = [item.arousal_score for item in global_train_examples]
    coarse_to_score = _coarse_class_score_mapping(arousal_train_scores, arousal_train)

    activity_model = _build_classifier(variant.classifier_kind)
    activity_model.fit(x_train, activity_train)
    arousal_model = _build_classifier(variant.classifier_kind)
    arousal_model.fit(x_train, arousal_train)

    prediction_payload = _subject_h5_predictions(
        global_train_examples=global_train_examples,
        subject_examples=test_examples,
        feature_names=feature_names,
        classifier_kind=variant.classifier_kind,
        global_activity_model=activity_model,
        global_arousal_model=arousal_model,
        coarse_to_score=coarse_to_score,
        calibration_segments=calibration_segments,
        adaptation_weight=adaptation_weight,
    )
    if not prediction_payload["eval_examples"]:
        raise ValueError("no evaluation examples after calibration split")
    for row in prediction_payload["per_subject_rows"]:
        row["variant_name"] = variant.variant_name

    eval_examples = prediction_payload["eval_examples"]
    truth_activity = [item.activity_label for item in eval_examples]
    truth_arousal = [item.arousal_coarse for item in eval_examples]
    global_activity_metrics = compute_classification_metrics(truth_activity, prediction_payload["global_activity_pred"])
    weak_activity_metrics = compute_classification_metrics(truth_activity, prediction_payload["weak_label_activity_pred"])
    label_free_activity_metrics = compute_classification_metrics(
        truth_activity,
        prediction_payload["label_free_activity_pred"],
    )
    global_arousal_metrics = compute_classification_metrics(truth_arousal, prediction_payload["global_arousal_pred"])
    weak_arousal_metrics = compute_classification_metrics(truth_arousal, prediction_payload["weak_label_arousal_pred"])
    label_free_arousal_metrics = compute_classification_metrics(
        truth_arousal,
        prediction_payload["label_free_arousal_pred"],
    )

    prediction_rows = _h5_prediction_rows(
        variant=variant,
        examples=eval_examples,
        global_activity_pred=prediction_payload["global_activity_pred"],
        weak_label_activity_pred=prediction_payload["weak_label_activity_pred"],
        label_free_activity_pred=prediction_payload["label_free_activity_pred"],
        global_arousal_pred=prediction_payload["global_arousal_pred"],
        weak_label_arousal_pred=prediction_payload["weak_label_arousal_pred"],
        label_free_arousal_pred=prediction_payload["label_free_arousal_pred"],
        coarse_to_score=coarse_to_score,
    )

    budget_rows: list[dict[str, Any]] = []
    for budget in sorted({1, calibration_segments, 2, 3, 4}):
        if budget < 1:
            continue
        budget_payload = _subject_h5_predictions(
            global_train_examples=global_train_examples,
            subject_examples=test_examples,
            feature_names=feature_names,
            classifier_kind=variant.classifier_kind,
            global_activity_model=activity_model,
            global_arousal_model=arousal_model,
            coarse_to_score=coarse_to_score,
            calibration_segments=budget,
            adaptation_weight=adaptation_weight,
        )
        if not budget_payload["eval_examples"]:
            continue
        budget_examples = budget_payload["eval_examples"]
        budget_truth_activity = [item.activity_label for item in budget_examples]
        budget_truth_arousal = [item.arousal_coarse for item in budget_examples]
        budget_rows.extend(
            [
                {
                    "variant_name": variant.variant_name,
                    "track": "activity",
                    "calibration_segments": budget,
                    "global_macro_f1": round(
                        compute_classification_metrics(budget_truth_activity, budget_payload["global_activity_pred"]).macro_f1,
                        6,
                    ),
                    "weak_label_macro_f1": round(
                        compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["weak_label_activity_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "label_free_macro_f1": round(
                        compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["label_free_activity_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "gain_weak_label_vs_global": round(
                        compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["weak_label_activity_pred"],
                        ).macro_f1
                        - compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["global_activity_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "gain_label_free_vs_global": round(
                        compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["label_free_activity_pred"],
                        ).macro_f1
                        - compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["global_activity_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "gain_label_free_vs_weak_label": round(
                        compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["label_free_activity_pred"],
                        ).macro_f1
                        - compute_classification_metrics(
                            budget_truth_activity,
                            budget_payload["weak_label_activity_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "eval_subjects": len({item.subject_id for item in budget_examples}),
                    "eval_segments": len(budget_examples),
                },
                {
                    "variant_name": variant.variant_name,
                    "track": "arousal_coarse",
                    "calibration_segments": budget,
                    "global_macro_f1": round(
                        compute_classification_metrics(budget_truth_arousal, budget_payload["global_arousal_pred"]).macro_f1,
                        6,
                    ),
                    "weak_label_macro_f1": round(
                        compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["weak_label_arousal_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "label_free_macro_f1": round(
                        compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["label_free_arousal_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "gain_weak_label_vs_global": round(
                        compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["weak_label_arousal_pred"],
                        ).macro_f1
                        - compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["global_arousal_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "gain_label_free_vs_global": round(
                        compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["label_free_arousal_pred"],
                        ).macro_f1
                        - compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["global_arousal_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "gain_label_free_vs_weak_label": round(
                        compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["label_free_arousal_pred"],
                        ).macro_f1
                        - compute_classification_metrics(
                            budget_truth_arousal,
                            budget_payload["weak_label_arousal_pred"],
                        ).macro_f1,
                        6,
                    ),
                    "eval_subjects": len({item.subject_id for item in budget_examples}),
                    "eval_segments": len(budget_examples),
                },
            ]
        )

    return H5WeakLabelLabelFreeVariantResult(
        variant_name=variant.variant_name,
        model_family=variant.model_family,
        classifier_kind=variant.classifier_kind,
        modality_group=variant.modality_group,
        input_modalities=list(variant.input_modalities),
        feature_names=feature_names,
        calibration_segments=calibration_segments,
        adaptation_weight=adaptation_weight,
        global_metrics={"activity": global_activity_metrics, "arousal_coarse": global_arousal_metrics},
        weak_label_metrics={"activity": weak_activity_metrics, "arousal_coarse": weak_arousal_metrics},
        label_free_metrics={"activity": label_free_activity_metrics, "arousal_coarse": label_free_arousal_metrics},
        per_subject_rows=prediction_payload["per_subject_rows"],
        prediction_rows=prediction_rows,
        budget_rows=budget_rows,
        split_summary={
            "global_train_subjects": len({item.subject_id for item in global_train_examples}),
            "global_train_segments": len(global_train_examples),
            "test_subjects": len({item.subject_id for item in test_examples}),
            "test_segments": len(test_examples),
            "eval_subjects_after_calibration": len({item.subject_id for item in eval_examples}),
            "eval_segments_after_calibration": len(eval_examples),
        },
    )


def _subject_calibration_predictions(
    subject_examples: list[SegmentExample],
    feature_names: list[str],
    activity_model: Any,
    arousal_model: Any,
    coarse_to_score: dict[str, int],
    calibration_segments: int,
) -> dict[str, Any]:
    grouped: dict[str, list[SegmentExample]] = {}
    for item in subject_examples:
        grouped.setdefault(item.subject_id, []).append(item)

    eval_examples: list[SegmentExample] = []
    global_activity_pred: list[str] = []
    personalized_activity_pred: list[str] = []
    global_arousal_pred: list[str] = []
    personalized_arousal_pred: list[str] = []
    per_subject_rows: list[dict[str, Any]] = []
    calibration_examples_by_subject: dict[str, list[SegmentExample]] = {}

    for subject_id in sorted(grouped.keys()):
        subject_rows = sorted(grouped[subject_id], key=_segment_sort_key)
        if len(subject_rows) <= calibration_segments:
            continue
        calibration_rows = subject_rows[:calibration_segments]
        eval_rows = subject_rows[calibration_segments:]

        x_calibration = _to_feature_matrix(calibration_rows, feature_names)
        x_eval = _to_feature_matrix(eval_rows, feature_names)

        subject_global_activity_cal = activity_model.predict(x_calibration)
        subject_global_arousal_cal = arousal_model.predict(x_calibration)
        subject_global_activity_eval = activity_model.predict(x_eval)
        subject_global_arousal_eval = arousal_model.predict(x_eval)

        activity_mapping = _subject_label_mapping(
            predicted=subject_global_activity_cal,
            truth=[item.activity_label for item in calibration_rows],
        )
        arousal_mapping = _subject_label_mapping(
            predicted=subject_global_arousal_cal,
            truth=[item.arousal_coarse for item in calibration_rows],
        )
        subject_personalized_activity_eval = [activity_mapping.get(item, item) for item in subject_global_activity_eval]
        subject_personalized_arousal_eval = [arousal_mapping.get(item, item) for item in subject_global_arousal_eval]

        truth_activity = [item.activity_label for item in eval_rows]
        truth_arousal = [item.arousal_coarse for item in eval_rows]
        global_activity_metrics = compute_classification_metrics(truth_activity, subject_global_activity_eval)
        personalized_activity_metrics = compute_classification_metrics(truth_activity, subject_personalized_activity_eval)
        global_arousal_metrics = compute_classification_metrics(truth_arousal, subject_global_arousal_eval)
        personalized_arousal_metrics = compute_classification_metrics(truth_arousal, subject_personalized_arousal_eval)

        per_subject_rows.extend(
            [
                {
                    "variant_name": "",
                    "track": "activity",
                    "subject_id": subject_id,
                    "global_macro_f1": global_activity_metrics.macro_f1,
                    "personalized_macro_f1": personalized_activity_metrics.macro_f1,
                    "gain_macro_f1": round(personalized_activity_metrics.macro_f1 - global_activity_metrics.macro_f1, 6),
                    "global_balanced_accuracy": global_activity_metrics.balanced_accuracy,
                    "personalized_balanced_accuracy": personalized_activity_metrics.balanced_accuracy,
                    "support": len(eval_rows),
                    "calibration_segments": len(calibration_rows),
                },
                {
                    "variant_name": "",
                    "track": "arousal_coarse",
                    "subject_id": subject_id,
                    "global_macro_f1": global_arousal_metrics.macro_f1,
                    "personalized_macro_f1": personalized_arousal_metrics.macro_f1,
                    "gain_macro_f1": round(personalized_arousal_metrics.macro_f1 - global_arousal_metrics.macro_f1, 6),
                    "global_balanced_accuracy": global_arousal_metrics.balanced_accuracy,
                    "personalized_balanced_accuracy": personalized_arousal_metrics.balanced_accuracy,
                    "support": len(eval_rows),
                    "calibration_segments": len(calibration_rows),
                },
            ]
        )

        calibration_examples_by_subject[subject_id] = calibration_rows
        eval_examples.extend(eval_rows)
        global_activity_pred.extend(subject_global_activity_eval)
        personalized_activity_pred.extend(subject_personalized_activity_eval)
        global_arousal_pred.extend(subject_global_arousal_eval)
        personalized_arousal_pred.extend(subject_personalized_arousal_eval)

    return {
        "eval_examples": eval_examples,
        "global_activity_pred": global_activity_pred,
        "personalized_activity_pred": personalized_activity_pred,
        "global_arousal_pred": global_arousal_pred,
        "personalized_arousal_pred": personalized_arousal_pred,
        "per_subject_rows": per_subject_rows,
        "coarse_to_score": coarse_to_score,
        "calibration_examples_by_subject": calibration_examples_by_subject,
    }


def _subject_full_personalization_predictions(
    global_train_examples: list[SegmentExample],
    subject_examples: list[SegmentExample],
    feature_names: list[str],
    classifier_kind: str,
    global_activity_model: Any,
    global_arousal_model: Any,
    coarse_to_score: dict[str, int],
    calibration_segments: int,
    adaptation_weight: int,
) -> dict[str, Any]:
    grouped: dict[str, list[SegmentExample]] = {}
    for item in subject_examples:
        grouped.setdefault(item.subject_id, []).append(item)

    eval_examples: list[SegmentExample] = []
    global_activity_pred: list[str] = []
    light_activity_pred: list[str] = []
    full_activity_pred: list[str] = []
    global_arousal_pred: list[str] = []
    light_arousal_pred: list[str] = []
    full_arousal_pred: list[str] = []
    per_subject_rows: list[dict[str, Any]] = []

    for subject_id in sorted(grouped.keys()):
        subject_rows = sorted(grouped[subject_id], key=_segment_sort_key)
        if len(subject_rows) <= calibration_segments:
            continue
        calibration_rows = subject_rows[:calibration_segments]
        eval_rows = subject_rows[calibration_segments:]

        x_calibration = _to_feature_matrix(calibration_rows, feature_names)
        x_eval = _to_feature_matrix(eval_rows, feature_names)
        truth_activity = [item.activity_label for item in eval_rows]
        truth_arousal = [item.arousal_coarse for item in eval_rows]

        subject_global_activity_cal = global_activity_model.predict(x_calibration)
        subject_global_arousal_cal = global_arousal_model.predict(x_calibration)
        subject_global_activity_eval = global_activity_model.predict(x_eval)
        subject_global_arousal_eval = global_arousal_model.predict(x_eval)

        activity_mapping = _subject_label_mapping(
            predicted=subject_global_activity_cal,
            truth=[item.activity_label for item in calibration_rows],
        )
        arousal_mapping = _subject_label_mapping(
            predicted=subject_global_arousal_cal,
            truth=[item.arousal_coarse for item in calibration_rows],
        )
        subject_light_activity_eval = [activity_mapping.get(item, item) for item in subject_global_activity_eval]
        subject_light_arousal_eval = [arousal_mapping.get(item, item) for item in subject_global_arousal_eval]

        augmented_rows = global_train_examples + (calibration_rows * adaptation_weight)
        x_augmented = _to_feature_matrix(augmented_rows, feature_names)
        y_activity_augmented = [item.activity_label for item in augmented_rows]
        y_arousal_augmented = [item.arousal_coarse for item in augmented_rows]
        full_activity_model = _build_classifier(classifier_kind)
        full_activity_model.fit(x_augmented, y_activity_augmented)
        full_arousal_model = _build_classifier(classifier_kind)
        full_arousal_model.fit(x_augmented, y_arousal_augmented)
        subject_full_activity_eval = full_activity_model.predict(x_eval)
        subject_full_arousal_eval = full_arousal_model.predict(x_eval)

        global_activity_metrics = compute_classification_metrics(truth_activity, subject_global_activity_eval)
        light_activity_metrics = compute_classification_metrics(truth_activity, subject_light_activity_eval)
        full_activity_metrics = compute_classification_metrics(truth_activity, subject_full_activity_eval)
        global_arousal_metrics = compute_classification_metrics(truth_arousal, subject_global_arousal_eval)
        light_arousal_metrics = compute_classification_metrics(truth_arousal, subject_light_arousal_eval)
        full_arousal_metrics = compute_classification_metrics(truth_arousal, subject_full_arousal_eval)

        per_subject_rows.extend(
            [
                {
                    "variant_name": "",
                    "track": "activity",
                    "subject_id": subject_id,
                    "global_macro_f1": global_activity_metrics.macro_f1,
                    "light_macro_f1": light_activity_metrics.macro_f1,
                    "full_macro_f1": full_activity_metrics.macro_f1,
                    "gain_light_vs_global": round(light_activity_metrics.macro_f1 - global_activity_metrics.macro_f1, 6),
                    "gain_full_vs_global": round(full_activity_metrics.macro_f1 - global_activity_metrics.macro_f1, 6),
                    "gain_full_vs_light": round(full_activity_metrics.macro_f1 - light_activity_metrics.macro_f1, 6),
                    "support": len(eval_rows),
                    "calibration_segments": len(calibration_rows),
                },
                {
                    "variant_name": "",
                    "track": "arousal_coarse",
                    "subject_id": subject_id,
                    "global_macro_f1": global_arousal_metrics.macro_f1,
                    "light_macro_f1": light_arousal_metrics.macro_f1,
                    "full_macro_f1": full_arousal_metrics.macro_f1,
                    "gain_light_vs_global": round(light_arousal_metrics.macro_f1 - global_arousal_metrics.macro_f1, 6),
                    "gain_full_vs_global": round(full_arousal_metrics.macro_f1 - global_arousal_metrics.macro_f1, 6),
                    "gain_full_vs_light": round(full_arousal_metrics.macro_f1 - light_arousal_metrics.macro_f1, 6),
                    "support": len(eval_rows),
                    "calibration_segments": len(calibration_rows),
                },
            ]
        )

        eval_examples.extend(eval_rows)
        global_activity_pred.extend(subject_global_activity_eval)
        light_activity_pred.extend(subject_light_activity_eval)
        full_activity_pred.extend(subject_full_activity_eval)
        global_arousal_pred.extend(subject_global_arousal_eval)
        light_arousal_pred.extend(subject_light_arousal_eval)
        full_arousal_pred.extend(subject_full_arousal_eval)

    return {
        "eval_examples": eval_examples,
        "global_activity_pred": global_activity_pred,
        "light_activity_pred": light_activity_pred,
        "full_activity_pred": full_activity_pred,
        "global_arousal_pred": global_arousal_pred,
        "light_arousal_pred": light_arousal_pred,
        "full_arousal_pred": full_arousal_pred,
        "per_subject_rows": per_subject_rows,
        "coarse_to_score": coarse_to_score,
    }


def _subject_h5_predictions(
    global_train_examples: list[SegmentExample],
    subject_examples: list[SegmentExample],
    feature_names: list[str],
    classifier_kind: str,
    global_activity_model: Any,
    global_arousal_model: Any,
    coarse_to_score: dict[str, int],
    calibration_segments: int,
    adaptation_weight: int,
) -> dict[str, Any]:
    del coarse_to_score
    grouped: dict[str, list[SegmentExample]] = {}
    for item in subject_examples:
        grouped.setdefault(item.subject_id, []).append(item)

    eval_examples: list[SegmentExample] = []
    global_activity_pred: list[str] = []
    weak_label_activity_pred: list[str] = []
    label_free_activity_pred: list[str] = []
    global_arousal_pred: list[str] = []
    weak_label_arousal_pred: list[str] = []
    label_free_arousal_pred: list[str] = []
    per_subject_rows: list[dict[str, Any]] = []

    global_x_train = _to_feature_matrix(global_train_examples, feature_names)
    global_activity_train = [item.activity_label for item in global_train_examples]
    global_arousal_train = [item.arousal_coarse for item in global_train_examples]

    for subject_id in sorted(grouped.keys()):
        subject_rows = sorted(grouped[subject_id], key=_segment_sort_key)
        if len(subject_rows) <= calibration_segments:
            continue
        calibration_rows = subject_rows[:calibration_segments]
        eval_rows = subject_rows[calibration_segments:]

        x_calibration = _to_feature_matrix(calibration_rows, feature_names)
        x_eval = _to_feature_matrix(eval_rows, feature_names)
        truth_activity = [item.activity_label for item in eval_rows]
        truth_arousal = [item.arousal_coarse for item in eval_rows]

        subject_global_activity_cal = global_activity_model.predict(x_calibration)
        subject_global_arousal_cal = global_arousal_model.predict(x_calibration)
        subject_global_activity_eval = global_activity_model.predict(x_eval)
        subject_global_arousal_eval = global_arousal_model.predict(x_eval)

        weak_activity_labels = _compose_weak_labels(
            truth=[item.activity_label for item in calibration_rows],
            pseudo=subject_global_activity_cal,
        )
        weak_arousal_labels = _compose_weak_labels(
            truth=[item.arousal_coarse for item in calibration_rows],
            pseudo=subject_global_arousal_cal,
        )
        label_free_activity_labels = list(subject_global_activity_cal)
        label_free_arousal_labels = list(subject_global_arousal_cal)

        weak_x_train = _augment_with_calibration(
            global_train=global_x_train,
            calibration=x_calibration,
            adaptation_weight=adaptation_weight,
        )
        weak_activity_y_train = global_activity_train + (weak_activity_labels * adaptation_weight)
        weak_arousal_y_train = global_arousal_train + (weak_arousal_labels * adaptation_weight)
        weak_activity_model = _build_classifier(classifier_kind)
        weak_activity_model.fit(weak_x_train, weak_activity_y_train)
        weak_arousal_model = _build_classifier(classifier_kind)
        weak_arousal_model.fit(weak_x_train, weak_arousal_y_train)
        subject_weak_activity_eval = weak_activity_model.predict(x_eval)
        subject_weak_arousal_eval = weak_arousal_model.predict(x_eval)

        label_free_x_train = _augment_with_calibration(
            global_train=global_x_train,
            calibration=x_calibration,
            adaptation_weight=adaptation_weight,
        )
        label_free_activity_y_train = global_activity_train + (label_free_activity_labels * adaptation_weight)
        label_free_arousal_y_train = global_arousal_train + (label_free_arousal_labels * adaptation_weight)
        label_free_activity_model = _build_classifier(classifier_kind)
        label_free_activity_model.fit(label_free_x_train, label_free_activity_y_train)
        label_free_arousal_model = _build_classifier(classifier_kind)
        label_free_arousal_model.fit(label_free_x_train, label_free_arousal_y_train)
        subject_label_free_activity_eval = label_free_activity_model.predict(x_eval)
        subject_label_free_arousal_eval = label_free_arousal_model.predict(x_eval)

        global_activity_metrics = compute_classification_metrics(truth_activity, subject_global_activity_eval)
        weak_activity_metrics = compute_classification_metrics(truth_activity, subject_weak_activity_eval)
        label_free_activity_metrics = compute_classification_metrics(truth_activity, subject_label_free_activity_eval)
        global_arousal_metrics = compute_classification_metrics(truth_arousal, subject_global_arousal_eval)
        weak_arousal_metrics = compute_classification_metrics(truth_arousal, subject_weak_arousal_eval)
        label_free_arousal_metrics = compute_classification_metrics(truth_arousal, subject_label_free_arousal_eval)

        per_subject_rows.extend(
            [
                {
                    "variant_name": "",
                    "track": "activity",
                    "subject_id": subject_id,
                    "global_macro_f1": global_activity_metrics.macro_f1,
                    "weak_label_macro_f1": weak_activity_metrics.macro_f1,
                    "label_free_macro_f1": label_free_activity_metrics.macro_f1,
                    "gain_weak_label_vs_global": round(weak_activity_metrics.macro_f1 - global_activity_metrics.macro_f1, 6),
                    "gain_label_free_vs_global": round(
                        label_free_activity_metrics.macro_f1 - global_activity_metrics.macro_f1,
                        6,
                    ),
                    "gain_label_free_vs_weak_label": round(
                        label_free_activity_metrics.macro_f1 - weak_activity_metrics.macro_f1,
                        6,
                    ),
                    "support": len(eval_rows),
                    "calibration_segments": len(calibration_rows),
                },
                {
                    "variant_name": "",
                    "track": "arousal_coarse",
                    "subject_id": subject_id,
                    "global_macro_f1": global_arousal_metrics.macro_f1,
                    "weak_label_macro_f1": weak_arousal_metrics.macro_f1,
                    "label_free_macro_f1": label_free_arousal_metrics.macro_f1,
                    "gain_weak_label_vs_global": round(weak_arousal_metrics.macro_f1 - global_arousal_metrics.macro_f1, 6),
                    "gain_label_free_vs_global": round(
                        label_free_arousal_metrics.macro_f1 - global_arousal_metrics.macro_f1,
                        6,
                    ),
                    "gain_label_free_vs_weak_label": round(
                        label_free_arousal_metrics.macro_f1 - weak_arousal_metrics.macro_f1,
                        6,
                    ),
                    "support": len(eval_rows),
                    "calibration_segments": len(calibration_rows),
                },
            ]
        )

        eval_examples.extend(eval_rows)
        global_activity_pred.extend(subject_global_activity_eval)
        weak_label_activity_pred.extend(subject_weak_activity_eval)
        label_free_activity_pred.extend(subject_label_free_activity_eval)
        global_arousal_pred.extend(subject_global_arousal_eval)
        weak_label_arousal_pred.extend(subject_weak_arousal_eval)
        label_free_arousal_pred.extend(subject_label_free_arousal_eval)

    return {
        "eval_examples": eval_examples,
        "global_activity_pred": global_activity_pred,
        "weak_label_activity_pred": weak_label_activity_pred,
        "label_free_activity_pred": label_free_activity_pred,
        "global_arousal_pred": global_arousal_pred,
        "weak_label_arousal_pred": weak_label_arousal_pred,
        "label_free_arousal_pred": label_free_arousal_pred,
        "per_subject_rows": per_subject_rows,
    }


def _augment_with_calibration(global_train: np.ndarray, calibration: np.ndarray, adaptation_weight: int) -> np.ndarray:
    if adaptation_weight <= 0 or calibration.shape[0] == 0:
        return global_train
    tiled = np.repeat(calibration, repeats=adaptation_weight, axis=0)
    return np.vstack([global_train, tiled])


def _compose_weak_labels(truth: list[str], pseudo: list[str]) -> list[str]:
    labels: list[str] = []
    for idx, (true_label, pseudo_label) in enumerate(zip(truth, pseudo)):
        labels.append(true_label if idx % 2 == 0 else pseudo_label)
    return labels


def _segment_sort_key(example: SegmentExample) -> tuple[int, str]:
    token = "".join(ch for ch in str(example.segment_id) if ch.isdigit())
    if token:
        return (0, f"{int(token):08d}")
    return (1, str(example.segment_id))


def _subject_label_mapping(predicted: list[str], truth: list[str]) -> dict[str, str]:
    grouped: dict[str, dict[str, int]] = {}
    for pred, actual in zip(predicted, truth):
        grouped.setdefault(pred, {})
        grouped[pred][actual] = grouped[pred].get(actual, 0) + 1
    mapping: dict[str, str] = {}
    for pred, counts in grouped.items():
        winner = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        mapping[pred] = winner
    return mapping


def _h2_prediction_rows(
    variant: VariantSpec,
    examples: list[SegmentExample],
    global_activity_pred: list[str],
    personalized_activity_pred: list[str],
    global_arousal_pred: list[str],
    personalized_arousal_pred: list[str],
    coarse_to_score: dict[str, int],
    subject_calibration_examples: dict[str, list[SegmentExample]],
) -> list[dict[str, Any]]:
    calibration_segments_index = {
        (item.subject_id, item.segment_id)
        for rows in subject_calibration_examples.values()
        for item in rows
    }
    rows: list[dict[str, Any]] = []
    for example, g_activity, p_activity, g_arousal, p_arousal in zip(
        examples,
        global_activity_pred,
        personalized_activity_pred,
        global_arousal_pred,
        personalized_arousal_pred,
    ):
        rows.append(
            {
                "variant_name": variant.variant_name,
                "model_family": variant.model_family,
                "classifier_kind": variant.classifier_kind,
                "modality_group": variant.modality_group,
                "subject_id": example.subject_id,
                "session_id": example.session_id,
                "segment_id": example.segment_id,
                "is_calibration_segment": (example.subject_id, example.segment_id) in calibration_segments_index,
                "activity_true": example.activity_label,
                "activity_global_pred": g_activity,
                "activity_personalized_pred": p_activity,
                "arousal_coarse_true": example.arousal_coarse,
                "arousal_coarse_global_pred": g_arousal,
                "arousal_coarse_personalized_pred": p_arousal,
                "arousal_score_true": example.arousal_score,
                "arousal_score_global_pred": coarse_to_score.get(g_arousal, 5),
                "arousal_score_personalized_pred": coarse_to_score.get(p_arousal, 5),
            }
        )
    return rows


def _h3_prediction_rows(
    variant: VariantSpec,
    examples: list[SegmentExample],
    global_activity_pred: list[str],
    light_activity_pred: list[str],
    full_activity_pred: list[str],
    global_arousal_pred: list[str],
    light_arousal_pred: list[str],
    full_arousal_pred: list[str],
    coarse_to_score: dict[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example, g_activity, l_activity, f_activity, g_arousal, l_arousal, f_arousal in zip(
        examples,
        global_activity_pred,
        light_activity_pred,
        full_activity_pred,
        global_arousal_pred,
        light_arousal_pred,
        full_arousal_pred,
    ):
        rows.append(
            {
                "variant_name": variant.variant_name,
                "model_family": variant.model_family,
                "classifier_kind": variant.classifier_kind,
                "modality_group": variant.modality_group,
                "subject_id": example.subject_id,
                "session_id": example.session_id,
                "segment_id": example.segment_id,
                "activity_true": example.activity_label,
                "activity_global_pred": g_activity,
                "activity_light_pred": l_activity,
                "activity_full_pred": f_activity,
                "arousal_coarse_true": example.arousal_coarse,
                "arousal_coarse_global_pred": g_arousal,
                "arousal_coarse_light_pred": l_arousal,
                "arousal_coarse_full_pred": f_arousal,
                "arousal_score_true": example.arousal_score,
                "arousal_score_global_pred": coarse_to_score.get(g_arousal, 5),
                "arousal_score_light_pred": coarse_to_score.get(l_arousal, 5),
                "arousal_score_full_pred": coarse_to_score.get(f_arousal, 5),
            }
        )
    return rows


def _h5_prediction_rows(
    variant: VariantSpec,
    examples: list[SegmentExample],
    global_activity_pred: list[str],
    weak_label_activity_pred: list[str],
    label_free_activity_pred: list[str],
    global_arousal_pred: list[str],
    weak_label_arousal_pred: list[str],
    label_free_arousal_pred: list[str],
    coarse_to_score: dict[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for example, g_activity, w_activity, l_activity, g_arousal, w_arousal, l_arousal in zip(
        examples,
        global_activity_pred,
        weak_label_activity_pred,
        label_free_activity_pred,
        global_arousal_pred,
        weak_label_arousal_pred,
        label_free_arousal_pred,
    ):
        rows.append(
            {
                "variant_name": variant.variant_name,
                "model_family": variant.model_family,
                "classifier_kind": variant.classifier_kind,
                "modality_group": variant.modality_group,
                "subject_id": example.subject_id,
                "session_id": example.session_id,
                "segment_id": example.segment_id,
                "activity_true": example.activity_label,
                "activity_global_pred": g_activity,
                "activity_weak_label_pred": w_activity,
                "activity_label_free_pred": l_activity,
                "arousal_coarse_true": example.arousal_coarse,
                "arousal_coarse_global_pred": g_arousal,
                "arousal_coarse_weak_label_pred": w_arousal,
                "arousal_coarse_label_free_pred": l_arousal,
                "arousal_score_true": example.arousal_score,
                "arousal_score_global_pred": coarse_to_score.get(g_arousal, 5),
                "arousal_score_weak_label_pred": coarse_to_score.get(w_arousal, 5),
                "arousal_score_label_free_pred": coarse_to_score.get(l_arousal, 5),
            }
        )
    return rows


def _build_h2_model_comparison_rows(variant_results: list[LightPersonalizationVariantResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in variant_results:
        for track in ("activity", "arousal_coarse"):
            global_metrics = result.global_metrics[track]
            personalized_metrics = result.personalized_metrics[track]
            delta = round(personalized_metrics.macro_f1 - global_metrics.macro_f1, 6)
            claim_status = "improved" if delta > 0 else ("regression" if delta < 0 else "inconclusive")
            rows.append(
                {
                    "variant_name": result.variant_name,
                    "model_family": result.model_family,
                    "classifier_kind": result.classifier_kind,
                    "modality_group": result.modality_group,
                    "track": track,
                    "evaluation_mode": "global",
                    "metric_name": "macro_f1",
                    "split": "test_eval_after_calibration",
                    "value": global_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": 0.0,
                    "claim_status": "baseline",
                    "support": sum(int(row["support"]) for row in result.per_subject_rows if row["track"] == track),
                }
            )
            rows.append(
                {
                    "variant_name": result.variant_name,
                    "model_family": result.model_family,
                    "classifier_kind": result.classifier_kind,
                    "modality_group": result.modality_group,
                    "track": track,
                    "evaluation_mode": "personalized",
                    "metric_name": "macro_f1",
                    "split": "test_eval_after_calibration",
                    "value": personalized_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": delta,
                    "claim_status": claim_status,
                    "support": sum(int(row["support"]) for row in result.per_subject_rows if row["track"] == track),
                }
            )
    return rows


def _build_h3_model_comparison_rows(variant_results: list[FullPersonalizationVariantResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in variant_results:
        for track in ("activity", "arousal_coarse"):
            global_metrics = result.global_metrics[track]
            light_metrics = result.light_metrics[track]
            full_metrics = result.full_metrics[track]
            light_delta = round(light_metrics.macro_f1 - global_metrics.macro_f1, 6)
            full_delta = round(full_metrics.macro_f1 - global_metrics.macro_f1, 6)
            full_vs_light = round(full_metrics.macro_f1 - light_metrics.macro_f1, 6)
            light_claim = "improved" if light_delta > 0 else ("regression" if light_delta < 0 else "inconclusive")
            full_claim = "improved" if full_delta > 0 else ("regression" if full_delta < 0 else "inconclusive")

            base_payload = {
                "variant_name": result.variant_name,
                "model_family": result.model_family,
                "classifier_kind": result.classifier_kind,
                "modality_group": result.modality_group,
                "track": track,
                "metric_name": "macro_f1",
                "split": "test_eval_after_calibration",
                "support": sum(int(row["support"]) for row in result.per_subject_rows if row["track"] == track),
            }
            rows.append(
                {
                    **base_payload,
                    "evaluation_mode": "global",
                    "value": global_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": 0.0,
                    "delta_vs_light": 0.0,
                    "claim_status": "baseline",
                }
            )
            rows.append(
                {
                    **base_payload,
                    "evaluation_mode": "light",
                    "value": light_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": light_delta,
                    "delta_vs_light": 0.0,
                    "claim_status": light_claim,
                }
            )
            rows.append(
                {
                    **base_payload,
                    "evaluation_mode": "full",
                    "value": full_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": full_delta,
                    "delta_vs_light": full_vs_light,
                    "claim_status": full_claim,
                }
            )
    return rows


def _build_h5_model_comparison_rows(
    variant_results: list[H5WeakLabelLabelFreeVariantResult],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in variant_results:
        for track in ("activity", "arousal_coarse"):
            global_metrics = result.global_metrics[track]
            weak_metrics = result.weak_label_metrics[track]
            label_free_metrics = result.label_free_metrics[track]
            weak_delta = round(weak_metrics.macro_f1 - global_metrics.macro_f1, 6)
            label_free_delta = round(label_free_metrics.macro_f1 - global_metrics.macro_f1, 6)
            label_free_vs_weak = round(label_free_metrics.macro_f1 - weak_metrics.macro_f1, 6)
            weak_claim = "improved" if weak_delta > 0 else ("regression" if weak_delta < 0 else "inconclusive")
            label_free_claim = (
                "improved" if label_free_delta > 0 else ("regression" if label_free_delta < 0 else "inconclusive")
            )

            base_payload = {
                "variant_name": result.variant_name,
                "model_family": result.model_family,
                "classifier_kind": result.classifier_kind,
                "modality_group": result.modality_group,
                "track": track,
                "metric_name": "macro_f1",
                "split": "test_eval_after_calibration",
                "support": sum(int(row["support"]) for row in result.per_subject_rows if row["track"] == track),
            }
            rows.append(
                {
                    **base_payload,
                    "evaluation_mode": "global",
                    "value": global_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": 0.0,
                    "delta_vs_weak_label": 0.0,
                    "claim_status": "baseline",
                }
            )
            rows.append(
                {
                    **base_payload,
                    "evaluation_mode": "weak_label",
                    "value": weak_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": weak_delta,
                    "delta_vs_weak_label": 0.0,
                    "claim_status": weak_claim,
                }
            )
            rows.append(
                {
                    **base_payload,
                    "evaluation_mode": "label_free",
                    "value": label_free_metrics.macro_f1,
                    "baseline_name": f"{result.variant_name}:global",
                    "baseline_value": global_metrics.macro_f1,
                    "delta_vs_global": label_free_delta,
                    "delta_vs_weak_label": label_free_vs_weak,
                    "claim_status": label_free_claim,
                }
            )
    return rows


def _build_examples(
    labels: list[dict[str, Any]],
    split_index: dict[str, str],
    raw_root: Path,
    dataset_id: str,
    dataset_version: str,
    min_confidence: float,
) -> list[SegmentExample]:
    examples: list[SegmentExample] = []
    subject_cache: dict[str, dict[str, np.ndarray]] = {}

    for row in labels:
        if row.get("dataset_id") != dataset_id or row.get("dataset_version") != dataset_version:
            continue
        if float(row.get("confidence", 0.0)) < min_confidence:
            continue
        start_index = row.get("source_segment_start_index")
        end_index = row.get("source_segment_end_index")
        if start_index is None or end_index is None:
            continue

        session_id = str(row["session_id"])
        subject_code = _subject_code_from_session_id(session_id)
        if subject_code is None:
            continue
        subject_id = f"{dataset_id}:{subject_code}"
        split = split_index.get(subject_id)
        if split is None:
            continue

        if subject_code not in subject_cache:
            subject_cache[subject_code] = _load_wesad_streams(raw_root=raw_root, subject_code=subject_code)
        streams = subject_cache[subject_code]
        feature_vector = _extract_multimodal_features(
            streams=streams,
            start_index=int(start_index),
            end_index=int(end_index),
        )
        if not feature_vector:
            continue

        arousal_score = int(row["arousal_score"])
        valence_score = int(row.get("valence_score", 5))
        examples.append(
            SegmentExample(
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                subject_id=subject_id,
                session_id=session_id,
                segment_id=str(row["segment_id"]),
                split=split,
                activity_label=str(row["activity_label"]),
                arousal_score=arousal_score,
                arousal_coarse=_arousal_coarse_class(arousal_score),
                valence_score=valence_score,
                valence_coarse=_valence_coarse_class(valence_score),
                source_label_value=str(row.get("source_label_value", "")),
                features=feature_vector,
            )
        )

    return examples


def _extract_multimodal_features(streams: dict[str, np.ndarray], start_index: int, end_index: int) -> dict[str, float]:
    if end_index < start_index:
        return {}

    start_sec = start_index / LABEL_RATE_HZ
    end_sec = (end_index + 1) / LABEL_RATE_HZ
    duration_sec = max(end_sec - start_sec, 0.0)
    features: dict[str, float] = {
        "meta_segment_duration_sec": round(duration_sec, 6),
        "meta_source_sample_count": float(end_index - start_index + 1),
    }
    for name in M7_9_CHEST_RR_FEATURE_NAMES + M7_9_POLAR_QUALITY_FEATURE_NAMES + M7_9_FUSION_FEATURE_NAMES:
        features[name] = 0.0

    _add_modality_group_features(
        features=features,
        streams=streams,
        modality_rates=WATCH_MODALITY_RATES_HZ,
        namespace="watch",
        start_sec=start_sec,
        end_sec=end_sec,
    )
    _add_modality_group_features(
        features=features,
        streams=streams,
        modality_rates=CHEST_MODALITY_RATES_HZ,
        namespace="chest",
        start_sec=start_sec,
        end_sec=end_sec,
    )
    _add_m7_9_fusion_proxy_features(features)
    return features


def _add_modality_group_features(
    features: dict[str, float],
    streams: dict[str, np.ndarray],
    modality_rates: dict[str, float],
    namespace: str,
    start_sec: float,
    end_sec: float,
) -> None:
    for modality, sample_rate in modality_rates.items():
        samples = streams.get(f"{namespace}:{modality}")
        if samples is None or len(samples) == 0:
            continue
        modality_start = int(np.floor(start_sec * sample_rate))
        modality_end = int(np.ceil(end_sec * sample_rate))
        modality_start = max(modality_start, 0)
        modality_end = min(modality_end, len(samples))
        if modality_end <= modality_start:
            continue

        chunk = samples[modality_start:modality_end]
        if chunk.ndim == 1:
            chunk = chunk.reshape(-1, 1)

        for col_index in range(chunk.shape[1]):
            col = chunk[:, col_index].astype(float)
            prefix = f"{namespace}_{modality.lower()}_c{col_index}"
            _add_channel_stats(features, prefix, col)

            if namespace == "chest" and modality == "ECG" and col_index == 0:
                _add_m7_9_rr_proxy_features_from_ecg(
                    features=features,
                    ecg_values=col,
                    sample_rate=sample_rate,
                )

        if modality == "ACC" and chunk.shape[1] >= 3:
            magnitude = np.sqrt(np.sum(chunk[:, :3].astype(float) ** 2, axis=1))
            _add_channel_stats(features, f"{namespace}_acc_mag", magnitude)


def _add_channel_stats(features: dict[str, float], prefix: str, values: np.ndarray) -> None:
    if values.size == 0:
        return
    features[f"{prefix}__mean"] = round(float(values.mean()), 6)
    features[f"{prefix}__std"] = round(float(values.std()), 6)
    features[f"{prefix}__min"] = round(float(values.min()), 6)
    features[f"{prefix}__max"] = round(float(values.max()), 6)
    features[f"{prefix}__last"] = round(float(values[-1]), 6)


def _add_m7_9_rr_proxy_features_from_ecg(
    *,
    features: dict[str, float],
    ecg_values: np.ndarray,
    sample_rate: float,
) -> None:
    if ecg_values.size < max(int(sample_rate * 2.0), 8):
        return
    centered = ecg_values.astype(float) - float(np.median(ecg_values))
    scale = float(np.std(centered))
    if not math.isfinite(scale) or scale <= 1e-9:
        return

    threshold = max(scale * 0.5, 1e-6)
    min_distance = max(1, int(sample_rate * 0.3))
    peaks: list[int] = []
    last_peak = -min_distance
    for index in range(1, centered.size - 1):
        current = centered[index]
        if current < threshold:
            continue
        if current < centered[index - 1] or current <= centered[index + 1]:
            continue
        if index - last_peak < min_distance:
            continue
        peaks.append(index)
        last_peak = index

    if len(peaks) < 2:
        return

    raw_rr_ms = np.diff(np.asarray(peaks, dtype=float)) * (1000.0 / sample_rate)
    if raw_rr_ms.size < 2:
        return
    valid_mask = (raw_rr_ms >= 250.0) & (raw_rr_ms <= 2500.0)
    rr_ms = raw_rr_ms[valid_mask]
    if rr_ms.size < 2:
        return

    rr_values = rr_ms.tolist()
    rr_diffs = np.diff(rr_ms)
    abs_diffs = np.abs(rr_diffs)

    mean_nn = float(np.mean(rr_ms))
    sdnn = float(np.std(rr_ms))
    rmssd = float(math.sqrt(np.mean(np.square(rr_diffs)))) if rr_diffs.size else 0.0
    sdsd = float(np.std(rr_diffs)) if rr_diffs.size else 0.0
    median_nn = float(np.median(rr_ms))
    iqr_nn = float(np.percentile(rr_ms, 75.0) - np.percentile(rr_ms, 25.0))
    mad_nn = float(np.median(np.abs(rr_ms - median_nn)))
    nn50 = float(np.sum(abs_diffs > 50.0)) if abs_diffs.size else 0.0
    pnn50 = float((nn50 / abs_diffs.size) * 100.0) if abs_diffs.size else 0.0
    cvnn = float((sdnn / mean_nn) * 100.0) if mean_nn > 0 else 0.0
    cvsd = float((rmssd / mean_nn) * 100.0) if mean_nn > 0 else 0.0

    hr_values = np.asarray([60000.0 / value for value in rr_values if value > 0], dtype=float)
    hr_mean = float(np.mean(hr_values)) if hr_values.size else 0.0
    hr_std = float(np.std(hr_values)) if hr_values.size else 0.0
    hr_min = float(np.min(hr_values)) if hr_values.size else 0.0
    hr_max = float(np.max(hr_values)) if hr_values.size else 0.0

    features.update(
        {
            "chest_rr_mean_nn": round(mean_nn, 6),
            "chest_rr_median_nn": round(median_nn, 6),
            "chest_rr_min_nn": round(float(np.min(rr_ms)), 6),
            "chest_rr_max_nn": round(float(np.max(rr_ms)), 6),
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
            "chest_rr_hr_min": round(hr_min, 6),
            "chest_rr_hr_max": round(hr_max, 6),
            "polar_quality_rr_coverage_ratio": round(float(rr_ms.size / raw_rr_ms.size), 6),
            "polar_quality_rr_valid_count": round(float(rr_ms.size), 6),
            "polar_quality_rr_outlier_ratio": round(float(1.0 - (rr_ms.size / raw_rr_ms.size)), 6),
        }
    )


def _add_m7_9_fusion_proxy_features(features: dict[str, float]) -> None:
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


def _load_wesad_streams(raw_root: Path, subject_code: str) -> dict[str, np.ndarray]:
    payload_path = raw_root / subject_code / f"{subject_code}.pkl"
    if not payload_path.exists():
        raise FileNotFoundError(f"missing WESAD subject pickle: {payload_path}")

    with payload_path.open("rb") as handle:
        payload = pickle.load(handle, encoding="latin1")

    wrist = payload["signal"]["wrist"]
    chest = payload["signal"]["chest"]
    return {
        "watch:ACC": np.asarray(wrist["ACC"], dtype=float),
        "watch:BVP": np.asarray(wrist["BVP"], dtype=float),
        "watch:EDA": np.asarray(wrist["EDA"], dtype=float),
        "watch:TEMP": np.asarray(wrist["TEMP"], dtype=float),
        "chest:ACC": np.asarray(chest["ACC"], dtype=float),
        "chest:ECG": np.asarray(chest["ECG"], dtype=float),
        "chest:EDA": np.asarray(chest["EDA"], dtype=float),
        "chest:EMG": np.asarray(chest["EMG"], dtype=float),
        "chest:Resp": np.asarray(chest["Resp"], dtype=float),
        "chest:Temp": np.asarray(chest["Temp"], dtype=float),
    }


def _select_feature_names(all_feature_names: list[str], prefixes: tuple[str, ...]) -> list[str]:
    return sorted(
        name
        for name in all_feature_names
        if name not in PROTOCOL_SHORTCUT_FEATURE_NAMES
        and any(name.startswith(prefix) for prefix in prefixes)
    )


def _to_feature_matrix(examples: list[SegmentExample], feature_names: list[str]) -> np.ndarray:
    if not examples:
        return np.zeros((0, len(feature_names)), dtype=float)
    matrix = np.zeros((len(examples), len(feature_names)), dtype=float)
    for row_index, item in enumerate(examples):
        for col_index, feature_name in enumerate(feature_names):
            matrix[row_index, col_index] = float(item.features.get(feature_name, 0.0))
    return matrix


def _classification_block(
    test_metrics: ClassificationMetrics,
    majority_metrics: ClassificationMetrics,
    validation_target: list[str],
    validation_predicted: list[str],
    test_target: list[str],
    test_predicted: list[str],
    subject_breakdown: list[dict[str, Any]],
    ci: dict[str, Any],
) -> dict[str, Any]:
    validation_metrics = compute_classification_metrics(validation_target, validation_predicted) if validation_target else None
    anti_collapse = _anti_collapse_diagnostics(test_target=test_target, test_predicted=test_predicted)
    return {
        "headline_metric": "macro_f1",
        "test": _classification_metrics_payload(test_metrics),
        "validation": _classification_metrics_payload(validation_metrics) if validation_metrics else None,
        "majority_class_baseline_test": _classification_metrics_payload(majority_metrics),
        "subject_level_breakdown_test": subject_breakdown,
        "uncertainty": ci,
        "delta_vs_majority_macro_f1": round(test_metrics.macro_f1 - majority_metrics.macro_f1, 6),
        "anti_collapse": anti_collapse,
    }


def _anti_collapse_diagnostics(test_target: list[str], test_predicted: list[str], dominance_threshold: float = 0.9) -> dict[str, Any]:
    if not test_predicted:
        return {
            "status": "empty",
            "passed": False,
            "target_unique_classes": len(set(test_target)),
            "predicted_unique_classes": 0,
            "unique_predicted_classes": 0,
            "dominant_class": None,
            "dominant_count": 0,
            "dominant_share": 0.0,
            "normalized_entropy": 0.0,
            "predicted_distribution": {},
        }

    counts = Counter(test_predicted)
    total = len(test_predicted)
    dominant_class, dominant_count = counts.most_common(1)[0]
    dominant_share = dominant_count / total
    unique_predicted_classes = len(counts)
    target_unique_classes = len(set(test_target))
    if unique_predicted_classes <= 1 and target_unique_classes >= 2:
        status = "collapsed"
        passed = False
    elif dominant_share >= dominance_threshold and target_unique_classes >= 2:
        status = "near_constant"
        passed = False
    elif target_unique_classes < 2:
        status = "insufficient_target_diversity"
        passed = True
    else:
        status = "ok"
        passed = True

    probabilities = [count / total for count in counts.values()]
    if unique_predicted_classes <= 1:
        normalized_entropy = 0.0
    else:
        entropy = -sum(prob * math.log(prob) for prob in probabilities if prob > 0.0)
        normalized_entropy = entropy / math.log(float(unique_predicted_classes))

    return {
        "status": status,
        "passed": passed,
        "target_unique_classes": target_unique_classes,
        "predicted_unique_classes": unique_predicted_classes,
        "unique_predicted_classes": unique_predicted_classes,
        "dominant_class": dominant_class,
        "dominant_count": dominant_count,
        "dominant_share": round(float(dominant_share), 6),
        "normalized_entropy": round(float(normalized_entropy), 6),
        "predicted_distribution": {
            label: round(float(count / total), 6) for label, count in sorted(counts.items(), key=lambda item: item[0])
        },
    }


def _classification_metrics_payload(metrics: ClassificationMetrics) -> dict[str, Any]:
    return {
        "macro_f1": metrics.macro_f1,
        "balanced_accuracy": metrics.balanced_accuracy,
        "weighted_f1": metrics.weighted_f1,
        "macro_recall": metrics.macro_recall,
        "labels": metrics.labels,
        "per_class_support": metrics.per_class_support,
        "confusion_matrix": metrics.confusion_matrix,
    }


def _subject_breakdown(examples: list[SegmentExample], predicted: list[str], target_field: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for example, pred in zip(examples, predicted):
        if example.subject_id not in grouped:
            grouped[example.subject_id] = {"truth": [], "pred": []}
        grouped[example.subject_id]["truth"].append(str(getattr(example, target_field)))
        grouped[example.subject_id]["pred"].append(pred)

    result = []
    for subject_id in sorted(grouped.keys()):
        metrics = compute_classification_metrics(grouped[subject_id]["truth"], grouped[subject_id]["pred"])
        result.append(
            {
                "subject_id": subject_id,
                "macro_f1": metrics.macro_f1,
                "balanced_accuracy": metrics.balanced_accuracy,
                "support": len(grouped[subject_id]["truth"]),
            }
        )
    return result


def _per_subject_metric_rows(
    variant_name: str,
    activity_rows: list[dict[str, Any]],
    arousal_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track_name, items in (("activity", activity_rows), ("arousal_coarse", arousal_rows)):
        for item in items:
            rows.append(
                {
                    "variant_name": variant_name,
                    "track": track_name,
                    "subject_id": item["subject_id"],
                    "macro_f1": item["macro_f1"],
                    "balanced_accuracy": item["balanced_accuracy"],
                    "support": item["support"],
                }
            )
    return rows


def _bootstrap_primary_metric_ci(
    examples: list[SegmentExample],
    predicted: list[str],
    baseline: list[str],
    target_field: str,
    seed: int = 42,
    iterations: int = 800,
) -> dict[str, Any]:
    grouped: dict[str, list[int]] = {}
    for idx, example in enumerate(examples):
        grouped.setdefault(example.subject_id, []).append(idx)

    subjects = sorted(grouped.keys())
    if len(subjects) < 2:
        return {
            "bootstrap_subjects": len(subjects),
            "bootstrap_iterations": 0,
            "primary_metric_ci95": [None, None],
            "delta_vs_baseline_ci95": [None, None],
        }

    rng = np.random.default_rng(seed)
    metric_samples = []
    delta_samples = []
    for _ in range(iterations):
        sampled_subjects = rng.choice(subjects, size=len(subjects), replace=True)
        indices: list[int] = []
        for subject in sampled_subjects:
            indices.extend(grouped[str(subject)])
        truth = [str(getattr(examples[i], target_field)) for i in indices]
        pred = [predicted[i] for i in indices]
        base = [baseline[i] for i in indices]
        m = compute_classification_metrics(truth, pred).macro_f1
        b = compute_classification_metrics(truth, base).macro_f1
        metric_samples.append(m)
        delta_samples.append(m - b)

    primary_ci = [round(float(np.percentile(metric_samples, 2.5)), 6), round(float(np.percentile(metric_samples, 97.5)), 6)]
    delta_ci = [round(float(np.percentile(delta_samples, 2.5)), 6), round(float(np.percentile(delta_samples, 97.5)), 6)]
    return {
        "bootstrap_subjects": len(subjects),
        "bootstrap_iterations": iterations,
        "primary_metric_ci95": primary_ci,
        "delta_vs_baseline_ci95": delta_ci,
    }


def _split_summary(examples: list[SegmentExample]) -> dict[str, Any]:
    if not examples:
        return {"subjects": 0, "sessions": 0, "segments": 0}
    subjects = {item.subject_id for item in examples}
    sessions = {item.session_id for item in examples}
    return {"subjects": len(subjects), "sessions": len(sessions), "segments": len(examples)}


def _exclusion_summary(labels: list[dict[str, Any]], min_confidence: float) -> dict[str, int]:
    low_confidence = 0
    missing_boundaries = 0
    for row in labels:
        if float(row.get("confidence", 0.0)) < min_confidence:
            low_confidence += 1
            continue
        if row.get("source_segment_start_index") is None or row.get("source_segment_end_index") is None:
            missing_boundaries += 1
    return {
        "low_confidence_segments": low_confidence,
        "missing_source_boundaries": missing_boundaries,
    }


def _prediction_rows(
    variant_name: str,
    model_family: str,
    examples: list[SegmentExample],
    activity_pred: list[str],
    arousal_pred: list[str],
    arousal_score_pred: list[int],
) -> list[dict[str, Any]]:
    rows = []
    for row, a_pred, c_pred, s_pred in zip(examples, activity_pred, arousal_pred, arousal_score_pred):
        rows.append(
            {
                "variant_name": variant_name,
                "model_family": model_family,
                "subject_id": row.subject_id,
                "session_id": row.session_id,
                "segment_id": row.segment_id,
                "source_label_value": row.source_label_value,
                "activity_true": row.activity_label,
                "activity_pred": a_pred,
                "arousal_coarse_true": row.arousal_coarse,
                "arousal_coarse_pred": c_pred,
                "arousal_score_true": row.arousal_score,
                "arousal_score_pred": s_pred,
            }
        )
    return rows


def _write_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "subject_id",
                "session_id",
                "segment_id",
                "source_label_value",
                "activity_true",
                "activity_pred",
                "arousal_coarse_true",
                "arousal_coarse_pred",
                "arousal_score_true",
                "arousal_score_pred",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _prediction_rows_e2_3(
    variant_name: str,
    model_family: str,
    examples: list[SegmentExample],
    arousal_pred: list[str],
    arousal_score_pred: list[int],
    valence_pred: list[str],
    valence_score_pred: list[int],
) -> list[dict[str, Any]]:
    rows = []
    for row, ar_pred, ar_score_pred, vl_pred, vl_score_pred in zip(
        examples,
        arousal_pred,
        arousal_score_pred,
        valence_pred,
        valence_score_pred,
    ):
        rows.append(
            {
                "variant_name": variant_name,
                "model_family": model_family,
                "subject_id": row.subject_id,
                "session_id": row.session_id,
                "segment_id": row.segment_id,
                "source_label_value": row.source_label_value,
                "arousal_coarse_true": row.arousal_coarse,
                "arousal_coarse_pred": ar_pred,
                "arousal_score_true": row.arousal_score,
                "arousal_score_pred": ar_score_pred,
                "valence_coarse_true": row.valence_coarse,
                "valence_coarse_pred": vl_pred,
                "valence_score_true": row.valence_score,
                "valence_score_pred": vl_score_pred,
            }
        )
    return rows


def _write_e2_3_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "subject_id",
                "session_id",
                "segment_id",
                "source_label_value",
                "arousal_coarse_true",
                "arousal_coarse_pred",
                "arousal_score_true",
                "arousal_score_pred",
                "valence_coarse_true",
                "valence_coarse_pred",
                "valence_score_true",
                "valence_score_pred",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_m7_3_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "subject_id",
                "session_id",
                "segment_id",
                "source_label_value",
                "activity_true",
                "activity_pred",
                "arousal_coarse_true",
                "arousal_coarse_pred",
                "arousal_score_true",
                "arousal_score_pred",
                "valence_coarse_true",
                "valence_coarse_pred",
                "valence_score_true",
                "valence_score_pred",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _per_subject_rows_for_tracks(
    variant_name: str,
    track_rows: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track_name, items in track_rows.items():
        for item in items:
            rows.append(
                {
                    "variant_name": variant_name,
                    "track": track_name,
                    "subject_id": item["subject_id"],
                    "macro_f1": item["macro_f1"],
                    "balanced_accuracy": item["balanced_accuracy"],
                    "support": item["support"],
                }
            )
    return rows


def _build_e2_3_model_comparison_rows(
    variant_results: list[dict[str, Any]],
    test_examples: list[SegmentExample],
    baseline_variant_name: str,
) -> list[dict[str, Any]]:
    by_name = {str(item["variant_name"]): item for item in variant_results}
    baseline = by_name[baseline_variant_name]
    rows: list[dict[str, Any]] = []

    for result in variant_results:
        for track_name, target_field, predicted_field in (
            ("arousal_coarse", "arousal_coarse", "arousal_test_pred"),
            ("valence_coarse", "valence_coarse", "valence_test_pred"),
        ):
            track = result["tracks"][track_name]
            baseline_track = baseline["tracks"][track_name]
            delta_ci = _bootstrap_pairwise_delta_ci(
                examples=test_examples,
                predicted_a=result[predicted_field],
                predicted_b=baseline[predicted_field],
                target_field=target_field,
            )
            delta_value = round(float(track["test"]["macro_f1"]) - float(baseline_track["test"]["macro_f1"]), 6)
            rows.append(
                {
                    "variant_name": result["variant_name"],
                    "track": track_name,
                    "metric_name": "macro_f1",
                    "split": "test",
                    "value": track["test"]["macro_f1"],
                    "baseline_name": baseline_variant_name,
                    "baseline_value": baseline_track["test"]["macro_f1"],
                    "delta_vs_watch_only": delta_value,
                    "delta_vs_watch_only_ci95_low": delta_ci[0],
                    "delta_vs_watch_only_ci95_high": delta_ci[1],
                    "claim_status": _claim_status_from_delta(delta_value=delta_value, delta_ci=delta_ci),
                    "delta_vs_majority": track["delta_vs_majority_macro_f1"],
                    "ci95_low": track["uncertainty"]["primary_metric_ci95"][0],
                    "ci95_high": track["uncertainty"]["primary_metric_ci95"][1],
                }
            )
    return rows


def _build_e2_3_research_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
) -> str:
    winners = report["comparison_summary"]
    lines = [
        "# E2.3 Polar/Watch Fusion-ready Benchmark",
        "",
        f"- Experiment: `{report['experiment_id']}`",
        f"- Dataset: `{report['dataset_version']}`",
        f"- Preprocessing: `{report['preprocessing_version']}`",
        "- Targets: `arousal_coarse`, `arousal_ordinal`, `valence_coarse`, `valence_ordinal (exploratory)`.",
        "",
        "## Winners",
        "",
        f"- Arousal coarse winner: `{winners['winner_arousal_coarse']['variant_name']}` (`macro_f1={float(winners['winner_arousal_coarse']['value']):.6f}`).",
        f"- Valence coarse winner: `{winners['winner_valence_coarse']['variant_name']}` (`macro_f1={float(winners['winner_valence_coarse']['value']):.6f}`).",
        "",
        "## Model Comparison (macro_f1, test)",
        "",
        "| Variant | Track | macro_f1 | delta_vs_polar_rr_only | claim |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in sorted(comparison_rows, key=lambda item: (str(item["track"]), -float(item["value"]))):
        lines.append(
            f"| {row['variant_name']} | {row['track']} | {float(row['value']):.6f} | "
            f"{float(row['delta_vs_watch_only']):.6f} | {row['claim_status']} |"
        )
    lines.extend(
        [
            "",
            "## Per-subject Coverage",
            "",
            f"- Rows: `{len(per_subject_rows)}`",
            "- Note: `valence` remains exploratory in this benchmark and should not be used as sole promotion gate.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_m7_3_polar_first_variants() -> list[VariantSpec]:
    return [
        VariantSpec(
            variant_name="polar_only",
            model_family="stochastic_gradient_linear_classifier",
            classifier_kind="sgd_linear",
            feature_prefixes=("chest_ecg_",),
            input_modalities=("polar_cardio_proxy(chest_ecg)",),
            description="Polar-first cardio-only ablation using ECG-derived proxy features.",
            modality_group="polar_only",
        ),
        VariantSpec(
            variant_name="watch_motion_only",
            model_family="stochastic_gradient_linear_classifier",
            classifier_kind="sgd_linear",
            feature_prefixes=("watch_acc_",),
            input_modalities=("watch_accelerometer",),
            description="Watch motion-only ablation using wrist accelerometer features.",
            modality_group="watch_motion_only",
        ),
        VariantSpec(
            variant_name="polar+watch_motion",
            model_family="stochastic_gradient_linear_classifier",
            classifier_kind="sgd_linear",
            feature_prefixes=("chest_ecg_", "watch_acc_"),
            input_modalities=("polar_cardio_proxy(chest_ecg)", "watch_accelerometer"),
            description="Polar-first combined cardio + watch motion ablation.",
            modality_group="polar_plus_watch_motion",
        ),
    ]


def _build_m7_9_polar_expanded_variants() -> list[VariantSpec]:
    return [
        VariantSpec(
            variant_name="polar_cardio_only",
            model_family="stochastic_gradient_linear_classifier",
            classifier_kind="sgd_linear",
            feature_prefixes=("chest_ecg_", "chest_rr_", "polar_quality_"),
            input_modalities=("polar_hr_proxy(chest_ecg)", "polar_rr_proxy(chest_rr)"),
            description="Polar cardio-only variant with HR proxy, RR/HRV proxy and quality indicators.",
            modality_group="polar_cardio_only",
        ),
        VariantSpec(
            variant_name="watch_motion_only",
            model_family="stochastic_gradient_linear_classifier",
            classifier_kind="sgd_linear",
            feature_prefixes=("watch_acc_",),
            input_modalities=("watch_accelerometer",),
            description="Watch motion-only ablation using accelerometer features.",
            modality_group="watch_motion_only",
        ),
        VariantSpec(
            variant_name="polar_expanded_fusion",
            model_family="stochastic_gradient_linear_classifier",
            classifier_kind="sgd_linear",
            feature_prefixes=("chest_ecg_", "chest_rr_", "watch_acc_", "fusion_hr_motion_", "polar_quality_"),
            input_modalities=("polar_hr_proxy(chest_ecg)", "polar_rr_proxy(chest_rr)", "watch_accelerometer"),
            description="Expanded fusion variant: Polar cardio + watch motion + cardio-motion coupling features.",
            modality_group="polar_expanded_fusion",
        ),
    ]


def _build_m7_9_report(
    experiment_id: str,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    split_manifest: dict[str, Any],
    labels: list[dict[str, Any]],
    min_confidence: float,
    examples: list[SegmentExample],
    variants: list[VariantSpec],
    variant_results: list[PolarFirstVariantResult],
    comparison_rows: list[dict[str, Any]],
    anti_collapse_summary: dict[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    winners_by_track: dict[str, dict[str, Any]] = {}
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        track_rows = [row for row in comparison_rows if row["track"] == track_name]
        best = _select_m7_3_winner_row(track_rows)
        winners_by_track[track_name] = {
            "variant_name": best["variant_name"],
            "model_family": best["model_family"],
            "classifier_kind": best["classifier_kind"],
            "modality_group": best["modality_group"],
            "value": best["value"],
            "claim_status": best["claim_status"],
            "delta_vs_polar_cardio_only": best["delta_vs_polar_only"],
            "anti_collapse_status": best["anti_collapse_status"],
            "anti_collapse_unique_predicted_classes": best["anti_collapse_unique_predicted_classes"],
            "anti_collapse_dominant_share": best["anti_collapse_dominant_share"],
        }

    split_summaries = {
        "train": variant_results[0].splits["train"] if variant_results else {"subjects": 0, "sessions": 0, "segments": 0},
        "validation": variant_results[0].splits["validation"] if variant_results else {"subjects": 0, "sessions": 0, "segments": 0},
        "test": variant_results[0].splits["test"] if variant_results else {"subjects": 0, "sessions": 0, "segments": 0},
    }

    return {
        "experiment_id": experiment_id,
        "run_kind": "m7-9-polar-expanded-fusion-benchmark",
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "comparison_goal": "Benchmark expanded Polar-first fusion with RR/HRV proxy and cardio-motion coupling features for activity/arousal/valence.",
        "research_hypothesis": "Expanded fusion should outperform polar-cardio-only and watch-motion-only variants on activity and arousal without anti-collapse regressions.",
        "status": "baseline",
        "targets": ["activity", "arousal_coarse", "valence_coarse"],
        "auxiliary_targets": ["arousal_ordinal", "valence_ordinal"],
        "variants": [
            {
                "variant_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "modality_group": item.modality_group,
                "input_modalities": list(item.input_modalities),
                "feature_count": len(result.feature_names),
                "description": item.description,
                "tracks": {
                    "activity": result.tracks["activity"],
                    "arousal_coarse": result.tracks["arousal_coarse"],
                    "valence_coarse": result.tracks["valence_coarse"],
                },
                "splits": result.splits,
            }
            for item, result in zip(variants, variant_results)
        ],
        "ablation_matrix": [
            {
                "variant_name": item.variant_name,
                "ablation_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "modality_group": item.modality_group,
                "input_modalities": list(item.input_modalities),
                "feature_prefixes": list(item.feature_prefixes),
                "description": item.description,
            }
            for item in variants
        ],
        "comparison_summary": {
            "winner_by_track": winners_by_track,
            "model_comparison": comparison_rows,
        },
        "anti_collapse_summary": anti_collapse_summary,
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "evaluation_subset": "wesad unified segment labels with confidence >= min_confidence on subject-wise split manifest",
            "subjects": len({item.subject_id for item in examples}),
            "sessions": len({item.session_id for item in examples}),
            "segments": len(examples),
            "split_summaries": split_summaries,
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "label_definition": {
            "targets": ["activity_label", "arousal_coarse", "valence_coarse"],
            "source_artifact": "unified/segment-labels.jsonl",
            "coarse_mapping": {"low": "1..3", "medium": "4..6", "high": "7..9"},
            "min_confidence": min_confidence,
        },
        "preprocessing": {
            "feature_families": {
                "polar_cardio_only": ["chest_ecg_*", "chest_rr_*", "polar_quality_*"],
                "watch_motion_only": ["watch_acc_*"],
                "polar_expanded_fusion": ["chest_ecg_*", "chest_rr_*", "watch_acc_*", "fusion_hr_motion_*", "polar_quality_*"],
            },
            "ablation_policy": "Expanded fusion adds RR/HRV proxy features and cardio-motion coupling while preserving watch-motion and cardio-only ablations.",
            "leakage_guards": [
                "subject-wise split manifest",
                "feature extraction only from raw signal windows inside labeled segment boundaries",
                "train-only standardization inside model wrappers when enabled",
            ],
        },
        "generated_at_utc": generated_at.isoformat(),
    }


def _build_m7_9_research_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
) -> str:
    winners = report["comparison_summary"]["winner_by_track"]
    anti_collapse_summary = report["anti_collapse_summary"]
    lines = [
        "# M7.9 Polar-Expanded Fusion Benchmark",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- `run_kind`: `{report['run_kind']}`",
        f"- Goal: {report['comparison_goal']}",
        f"- Activity winner: `{winners['activity']['variant_name']}` (`macro_f1={winners['activity']['value']}`, `claim={winners['activity']['claim_status']}`).",
        f"- Arousal winner: `{winners['arousal_coarse']['variant_name']}` (`macro_f1={winners['arousal_coarse']['value']}`, `claim={winners['arousal_coarse']['claim_status']}`).",
        f"- Valence winner: `{winners['valence_coarse']['variant_name']}` (`macro_f1={winners['valence_coarse']['value']}`, `claim={winners['valence_coarse']['claim_status']}`).",
        "",
        "## Ablation Matrix",
        "",
        "| Variant | Scope | Family | Features |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["ablation_matrix"]:
        lines.append(
            f"| {item['variant_name']} | {item['modality_group']} | {item['classifier_kind']} | {', '.join(item['feature_prefixes'])} |"
        )
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Variant | Track | macro_f1 | delta_vs_polar_cardio_only | claim | anti-collapse |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in sorted(comparison_rows, key=lambda item: (item["track"], -float(item["value"]))):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {float(row['value']):.6f} | "
            f"{float(row['delta_vs_polar_only']):.6f} | {row['claim_status']} | {row['anti_collapse_status']} |"
        )

    flagged = anti_collapse_summary["flagged_rows"]
    lines.extend(
        [
            "",
            "## Anti-collapse Check",
            "",
            f"- Threshold: `{anti_collapse_summary['threshold']}`",
            f"- Passed: `{anti_collapse_summary['passed']}`",
        ]
    )
    if flagged:
        lines.append("- Flagged rows:")
        for row in flagged:
            lines.append(
                f"  - `{row['variant_name']}` / `{row['track']}` -> `{row['status']}` "
                f"(dominant_share={row['dominant_share']}, unique={row['unique_predicted_classes']})"
            )
    else:
        lines.append("- No near-constant predictions detected on test rows.")

    lines.extend(
        [
            "",
            "## Subject-level Coverage",
            "",
            f"- Per-subject rows: `{len(per_subject_rows)}`",
            "- Polar-expanded claim remains valid only when anti-collapse and winner claim statuses stay green across all tracks.",
            "",
        ]
    )
    return "\n".join(lines)


def _select_m7_3_winner_row(track_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _priority(row: dict[str, Any]) -> tuple[int, float, float, str]:
        claim_status = str(row.get("claim_status") or "")
        anti_collapse_status = str(row.get("anti_collapse_status") or "")
        if claim_status == "supported" and anti_collapse_status == "ok":
            tier = 0
        elif claim_status == "supported":
            tier = 1
        elif anti_collapse_status == "ok":
            tier = 2
        else:
            tier = 3

        value_raw = row.get("value")
        value = float(value_raw) if value_raw is not None else float("-inf")
        delta = row.get("delta_vs_polar_only")
        if delta is None:
            delta = row.get("delta_vs_watch_only")
        delta_value = float(delta) if delta is not None else float("-inf")
        return (tier, -value, -delta_value, str(row.get("variant_name") or ""))

    if not track_rows:
        raise ValueError("cannot select winner from empty track rows")
    return min(track_rows, key=_priority)


def _evaluate_polar_first_variant(
    examples: list[SegmentExample],
    variant: VariantSpec,
) -> PolarFirstVariantResult:
    all_feature_names = sorted(examples[0].features.keys())
    feature_names = _select_feature_names(all_feature_names, variant.feature_prefixes)
    if not feature_names:
        raise ValueError(f"variant {variant.variant_name} has no feature set")

    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    test_examples = [item for item in examples if item.split == "test"]
    if not train_examples or not test_examples:
        raise ValueError("insufficient split coverage: train and test must be non-empty")

    x_train = _to_feature_matrix(train_examples, feature_names)
    x_validation = _to_feature_matrix(validation_examples, feature_names)
    x_test = _to_feature_matrix(test_examples, feature_names)

    activity_train = [item.activity_label for item in train_examples]
    activity_validation = [item.activity_label for item in validation_examples]
    activity_test = [item.activity_label for item in test_examples]

    arousal_train_scores = [item.arousal_score for item in train_examples]
    arousal_validation_scores = [item.arousal_score for item in validation_examples]
    arousal_test_scores = [item.arousal_score for item in test_examples]
    arousal_train = [item.arousal_coarse for item in train_examples]
    arousal_validation = [item.arousal_coarse for item in validation_examples]
    arousal_test = [item.arousal_coarse for item in test_examples]

    valence_train_scores = [item.valence_score for item in train_examples]
    valence_validation_scores = [item.valence_score for item in validation_examples]
    valence_test_scores = [item.valence_score for item in test_examples]
    valence_train = [item.valence_coarse for item in train_examples]
    valence_validation = [item.valence_coarse for item in validation_examples]
    valence_test = [item.valence_coarse for item in test_examples]

    activity_model = _build_classifier(variant.classifier_kind)
    activity_model.fit(x_train, activity_train)
    activity_validation_pred = activity_model.predict(x_validation)
    activity_test_pred = activity_model.predict(x_test)

    arousal_model = _build_classifier(variant.classifier_kind)
    arousal_model.fit(x_train, arousal_train)
    arousal_validation_pred = arousal_model.predict(x_validation)
    arousal_test_pred = arousal_model.predict(x_test)

    valence_model = _build_classifier(variant.classifier_kind)
    valence_model.fit(x_train, valence_train)
    valence_validation_pred = valence_model.predict(x_validation)
    valence_test_pred = valence_model.predict(x_test)

    arousal_coarse_to_score = _coarse_class_score_mapping(arousal_train_scores, arousal_train)
    arousal_test_score_pred = [arousal_coarse_to_score.get(label, 5) for label in arousal_test_pred]
    valence_coarse_to_score = _coarse_class_score_mapping(valence_train_scores, valence_train)
    valence_test_score_pred = [valence_coarse_to_score.get(label, 5) for label in valence_test_pred]

    activity_majority = _majority_label(activity_train)
    arousal_majority = _majority_label(arousal_train)
    valence_majority = _majority_label(valence_train)
    arousal_median = int(round(float(np.median(np.asarray(arousal_train_scores, dtype=float)))))
    valence_median = int(round(float(np.median(np.asarray(valence_train_scores, dtype=float)))))

    activity_test_metrics = compute_classification_metrics(activity_test, activity_test_pred)
    activity_test_majority_metrics = compute_classification_metrics(activity_test, [activity_majority] * len(activity_test))
    arousal_test_metrics = compute_classification_metrics(arousal_test, arousal_test_pred)
    arousal_test_majority_metrics = compute_classification_metrics(arousal_test, [arousal_majority] * len(arousal_test))
    valence_test_metrics = compute_classification_metrics(valence_test, valence_test_pred)
    valence_test_majority_metrics = compute_classification_metrics(valence_test, [valence_majority] * len(valence_test))

    arousal_test_ordinal = {
        "mae": compute_mae(arousal_test_scores, arousal_test_score_pred),
        "spearman_rho": compute_spearman_rho(arousal_test_scores, arousal_test_score_pred),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            arousal_test_scores,
            arousal_test_score_pred,
            min_rating=1,
            max_rating=9,
        ),
    }
    arousal_test_ordinal_median = {
        "mae": compute_mae(arousal_test_scores, [arousal_median] * len(arousal_test_scores)),
        "spearman_rho": compute_spearman_rho(arousal_test_scores, [arousal_median] * len(arousal_test_scores)),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            arousal_test_scores,
            [arousal_median] * len(arousal_test_scores),
            min_rating=1,
            max_rating=9,
        ),
    }
    valence_test_ordinal = {
        "mae": compute_mae(valence_test_scores, valence_test_score_pred),
        "spearman_rho": compute_spearman_rho(valence_test_scores, valence_test_score_pred),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            valence_test_scores,
            valence_test_score_pred,
            min_rating=1,
            max_rating=9,
        ),
    }
    valence_test_ordinal_median = {
        "mae": compute_mae(valence_test_scores, [valence_median] * len(valence_test_scores)),
        "spearman_rho": compute_spearman_rho(valence_test_scores, [valence_median] * len(valence_test_scores)),
        "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
            valence_test_scores,
            [valence_median] * len(valence_test_scores),
            min_rating=1,
            max_rating=9,
        ),
    }

    subject_breakdown_activity = _subject_breakdown(
        examples=test_examples,
        predicted=activity_test_pred,
        target_field="activity_label",
    )
    subject_breakdown_arousal = _subject_breakdown(
        examples=test_examples,
        predicted=arousal_test_pred,
        target_field="arousal_coarse",
    )
    subject_breakdown_valence = _subject_breakdown(
        examples=test_examples,
        predicted=valence_test_pred,
        target_field="valence_coarse",
    )
    activity_ci = _bootstrap_primary_metric_ci(
        examples=test_examples,
        predicted=activity_test_pred,
        baseline=[activity_majority] * len(activity_test),
        target_field="activity_label",
    )
    arousal_ci = _bootstrap_primary_metric_ci(
        examples=test_examples,
        predicted=arousal_test_pred,
        baseline=[arousal_majority] * len(arousal_test),
        target_field="arousal_coarse",
    )
    valence_ci = _bootstrap_primary_metric_ci(
        examples=test_examples,
        predicted=valence_test_pred,
        baseline=[valence_majority] * len(valence_test),
        target_field="valence_coarse",
    )

    tracks = {
        "activity": _classification_block(
            test_metrics=activity_test_metrics,
            majority_metrics=activity_test_majority_metrics,
            validation_target=activity_validation,
            validation_predicted=activity_validation_pred,
            test_target=activity_test,
            test_predicted=activity_test_pred,
            subject_breakdown=subject_breakdown_activity,
            ci=activity_ci,
        ),
        "arousal_coarse": _classification_block(
            test_metrics=arousal_test_metrics,
            majority_metrics=arousal_test_majority_metrics,
            validation_target=arousal_validation,
            validation_predicted=arousal_validation_pred,
            test_target=arousal_test,
            test_predicted=arousal_test_pred,
            subject_breakdown=subject_breakdown_arousal,
            ci=arousal_ci,
        ),
        "arousal_ordinal": {
            "test": arousal_test_ordinal,
            "global_median_predictor_test": arousal_test_ordinal_median,
        },
        "valence_coarse": _classification_block(
            test_metrics=valence_test_metrics,
            majority_metrics=valence_test_majority_metrics,
            validation_target=valence_validation,
            validation_predicted=valence_validation_pred,
            test_target=valence_test,
            test_predicted=valence_test_pred,
            subject_breakdown=subject_breakdown_valence,
            ci=valence_ci,
        ),
        "valence_ordinal": {
            "test": valence_test_ordinal,
            "global_median_predictor_test": valence_test_ordinal_median,
        },
    }

    per_subject_rows = _per_subject_rows_for_tracks(
        variant_name=variant.variant_name,
        track_rows={
            "activity": subject_breakdown_activity,
            "arousal_coarse": subject_breakdown_arousal,
            "valence_coarse": subject_breakdown_valence,
        },
    )
    prediction_rows = _polar_first_prediction_rows(
        variant=variant,
        examples=test_examples,
        activity_pred=activity_test_pred,
        arousal_pred=arousal_test_pred,
        arousal_score_pred=arousal_test_score_pred,
        valence_pred=valence_test_pred,
        valence_score_pred=valence_test_score_pred,
    )

    return PolarFirstVariantResult(
        variant_name=variant.variant_name,
        model_family=variant.model_family,
        classifier_kind=variant.classifier_kind,
        modality_group=variant.modality_group,
        input_modalities=list(variant.input_modalities),
        feature_names=feature_names,
        activity_test_pred=activity_test_pred,
        arousal_test_pred=arousal_test_pred,
        valence_test_pred=valence_test_pred,
        arousal_test_score_pred=arousal_test_score_pred,
        valence_test_score_pred=valence_test_score_pred,
        tracks=tracks,
        splits={
            "train": _split_summary(train_examples),
            "validation": _split_summary(validation_examples),
            "test": _split_summary(test_examples),
        },
        per_subject_rows=per_subject_rows,
        prediction_rows=prediction_rows,
    )


def _polar_first_prediction_rows(
    variant: VariantSpec,
    examples: list[SegmentExample],
    activity_pred: list[str],
    arousal_pred: list[str],
    arousal_score_pred: list[int],
    valence_pred: list[str],
    valence_score_pred: list[int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row, activity_item, arousal_item, arousal_score_item, valence_item, valence_score_item in zip(
        examples,
        activity_pred,
        arousal_pred,
        arousal_score_pred,
        valence_pred,
        valence_score_pred,
    ):
        rows.append(
            {
                "variant_name": variant.variant_name,
                "model_family": variant.model_family,
                "classifier_kind": variant.classifier_kind,
                "modality_group": variant.modality_group,
                "subject_id": row.subject_id,
                "session_id": row.session_id,
                "segment_id": row.segment_id,
                "source_label_value": row.source_label_value,
                "activity_true": row.activity_label,
                "activity_pred": activity_item,
                "arousal_coarse_true": row.arousal_coarse,
                "arousal_coarse_pred": arousal_item,
                "arousal_score_true": row.arousal_score,
                "arousal_score_pred": arousal_score_item,
                "valence_coarse_true": row.valence_coarse,
                "valence_coarse_pred": valence_item,
                "valence_score_true": row.valence_score,
                "valence_score_pred": valence_score_item,
            }
        )
    return rows


def _build_m7_3_model_comparison_rows(
    variant_results: list[PolarFirstVariantResult],
    test_examples: list[SegmentExample],
    baseline_variant_name: str,
) -> list[dict[str, Any]]:
    by_name = {item.variant_name: item for item in variant_results}
    baseline = by_name[baseline_variant_name]
    rows: list[dict[str, Any]] = []
    for result in variant_results:
        for track_name, target_field, predicted_field in (
            ("activity", "activity_label", "activity_test_pred"),
            ("arousal_coarse", "arousal_coarse", "arousal_test_pred"),
            ("valence_coarse", "valence_coarse", "valence_test_pred"),
        ):
            track = result.tracks[track_name]
            baseline_track = baseline.tracks[track_name]
            delta_ci = _bootstrap_pairwise_delta_ci(
                examples=test_examples,
                predicted_a=getattr(result, predicted_field),
                predicted_b=getattr(baseline, predicted_field),
                target_field=target_field,
            )
            delta_value = round(float(track["test"]["macro_f1"]) - float(baseline_track["test"]["macro_f1"]), 6)
            anti_collapse = track["anti_collapse"]
            rows.append(
                {
                    "variant_name": result.variant_name,
                    "model_family": result.model_family,
                    "classifier_kind": result.classifier_kind,
                    "modality_group": result.modality_group,
                    "track": track_name,
                    "metric_name": "macro_f1",
                    "split": "test",
                    "value": track["test"]["macro_f1"],
                    "baseline_name": baseline_variant_name,
                    "baseline_value": baseline_track["test"]["macro_f1"],
                    "delta_vs_polar_only": delta_value,
                    "delta_vs_polar_only_ci95_low": delta_ci[0],
                    "delta_vs_polar_only_ci95_high": delta_ci[1],
                    "delta_vs_watch_only": delta_value,
                    "delta_vs_watch_only_ci95_low": delta_ci[0],
                    "delta_vs_watch_only_ci95_high": delta_ci[1],
                    "claim_status": _claim_status_from_delta(delta_value=delta_value, delta_ci=delta_ci),
                    "delta_vs_majority": track["delta_vs_majority_macro_f1"],
                    "ci95_low": track["uncertainty"]["primary_metric_ci95"][0],
                    "ci95_high": track["uncertainty"]["primary_metric_ci95"][1],
                    "anti_collapse_status": anti_collapse["status"],
                    "anti_collapse_unique_predicted_classes": anti_collapse["unique_predicted_classes"],
                    "anti_collapse_dominant_share": anti_collapse["dominant_share"],
                }
            )
    return rows


def _build_anti_collapse_summary(variant_results: list[PolarFirstVariantResult]) -> dict[str, Any]:
    per_variant: dict[str, dict[str, Any]] = {}
    flagged_rows: list[dict[str, Any]] = []
    for result in variant_results:
        track_payload: dict[str, Any] = {}
        for track_name in ("activity", "arousal_coarse", "valence_coarse"):
            anti_collapse = result.tracks[track_name]["anti_collapse"]
            track_payload[track_name] = anti_collapse
            if anti_collapse["status"] in {"collapsed", "near_constant"}:
                flagged_rows.append(
                    {
                        "variant_name": result.variant_name,
                        "track": track_name,
                        **anti_collapse,
                    }
                )
        per_variant[result.variant_name] = track_payload
    return {
        "threshold": 0.9,
        "passed": not flagged_rows,
        "per_variant": per_variant,
        "flagged_rows": flagged_rows,
    }


def _build_m7_3_report(
    experiment_id: str,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    split_manifest: dict[str, Any],
    labels: list[dict[str, Any]],
    min_confidence: float,
    examples: list[SegmentExample],
    variants: list[VariantSpec],
    variant_results: list[PolarFirstVariantResult],
    comparison_rows: list[dict[str, Any]],
    anti_collapse_summary: dict[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    winners_by_track = {}
    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        track_rows = [row for row in comparison_rows if row["track"] == track_name]
        best = _select_m7_3_winner_row(track_rows)
        winners_by_track[track_name] = {
            "variant_name": best["variant_name"],
            "model_family": best["model_family"],
            "classifier_kind": best["classifier_kind"],
            "modality_group": best["modality_group"],
            "value": best["value"],
            "claim_status": best["claim_status"],
            "delta_vs_polar_only": best["delta_vs_polar_only"],
            "anti_collapse_status": best["anti_collapse_status"],
            "anti_collapse_unique_predicted_classes": best["anti_collapse_unique_predicted_classes"],
            "anti_collapse_dominant_share": best["anti_collapse_dominant_share"],
        }

    split_summaries = {
        "train": variant_results[0].splits["train"] if variant_results else {"subjects": 0, "sessions": 0, "segments": 0},
        "validation": variant_results[0].splits["validation"] if variant_results else {"subjects": 0, "sessions": 0, "segments": 0},
        "test": variant_results[0].splits["test"] if variant_results else {"subjects": 0, "sessions": 0, "segments": 0},
    }

    return {
        "experiment_id": experiment_id,
        "run_kind": "m7-3-polar-first-training-dataset-build",
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "comparison_goal": "Build a claim-grade Polar-first training benchmark with activity, arousal and valence targets across the required ablations.",
        "research_hypothesis": "Polar cardio features should dominate arousal and valence, while watch motion remains necessary for activity and should help the combined ablation across all targets.",
        "status": "baseline",
        "targets": ["activity", "arousal_coarse", "valence_coarse"],
        "auxiliary_targets": ["arousal_ordinal", "valence_ordinal"],
        "variants": [
            {
                "variant_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "modality_group": item.modality_group,
                "input_modalities": list(item.input_modalities),
                "feature_count": len(result.feature_names),
                "description": item.description,
                "tracks": {
                    "activity": result.tracks["activity"],
                    "arousal_coarse": result.tracks["arousal_coarse"],
                    "valence_coarse": result.tracks["valence_coarse"],
                },
                "splits": result.splits,
            }
            for item, result in zip(variants, variant_results)
        ],
        "ablation_matrix": [
            {
                "variant_name": item.variant_name,
                "ablation_name": item.variant_name,
                "model_family": item.model_family,
                "classifier_kind": item.classifier_kind,
                "modality_group": item.modality_group,
                "input_modalities": list(item.input_modalities),
                "feature_prefixes": list(item.feature_prefixes),
                "description": item.description,
            }
            for item in variants
        ],
        "comparison_summary": {
            "winner_by_track": winners_by_track,
            "model_comparison": comparison_rows,
        },
        "anti_collapse_summary": anti_collapse_summary,
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "evaluation_subset": "wesad unified segment labels with confidence >= min_confidence on subject-wise split manifest",
            "subjects": len({item.subject_id for item in examples}),
            "sessions": len({item.session_id for item in examples}),
            "segments": len(examples),
            "split_summaries": split_summaries,
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "label_definition": {
            "targets": ["activity_label", "arousal_coarse", "valence_coarse"],
            "source_artifact": "unified/segment-labels.jsonl",
            "coarse_mapping": {"low": "1..3", "medium": "4..6", "high": "7..9"},
            "min_confidence": min_confidence,
        },
        "preprocessing": {
            "feature_families": {
                "polar_only": ["chest_ecg_*"],
                "watch_motion_only": ["watch_acc_*"],
                "polar_plus_watch_motion": ["chest_ecg_*", "watch_acc_*"],
            },
            "ablation_policy": "Polar H10 cardio proxy is isolated from watch motion to make the ablation matrix explicit.",
            "leakage_guards": [
                "subject-wise split manifest",
                "feature extraction only from raw signal windows inside labeled segment boundaries",
                "train-only standardization inside model wrappers when enabled",
            ],
        },
        "generated_at_utc": generated_at.isoformat(),
    }


def _build_m7_3_research_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
) -> str:
    winners = report["comparison_summary"]["winner_by_track"]
    anti_collapse_summary = report["anti_collapse_summary"]
    lines = [
        "# M7.3 Polar-first Training Dataset Build",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- `run_kind`: `{report['run_kind']}`",
        f"- Goal: {report['comparison_goal']}",
        f"- Activity winner: `{winners['activity']['variant_name']}` (`macro_f1={winners['activity']['value']}`, `claim={winners['activity']['claim_status']}`).",
        f"- Arousal winner: `{winners['arousal_coarse']['variant_name']}` (`macro_f1={winners['arousal_coarse']['value']}`, `claim={winners['arousal_coarse']['claim_status']}`).",
        f"- Valence winner: `{winners['valence_coarse']['variant_name']}` (`macro_f1={winners['valence_coarse']['value']}`, `claim={winners['valence_coarse']['claim_status']}`).",
        "",
        "## Ablation Matrix",
        "",
        "| Variant | Scope | Family | Features |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["ablation_matrix"]:
        lines.append(
            f"| {item['variant_name']} | {item['modality_group']} | {item['classifier_kind']} | {', '.join(item['feature_prefixes'])} |"
        )
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Variant | Track | macro_f1 | delta_vs_polar_only | claim | anti-collapse |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in sorted(comparison_rows, key=lambda item: (item["track"], -float(item["value"]))):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {float(row['value']):.6f} | "
            f"{float(row['delta_vs_polar_only']):.6f} | {row['claim_status']} | {row['anti_collapse_status']} |"
        )

    flagged = anti_collapse_summary["flagged_rows"]
    lines.extend(
        [
            "",
            "## Anti-collapse Check",
            "",
            f"- Threshold: `{anti_collapse_summary['threshold']}`",
            f"- Passed: `{anti_collapse_summary['passed']}`",
        ]
    )
    if flagged:
        lines.append("- Flagged rows:")
        for row in flagged:
            lines.append(
                f"  - `{row['variant_name']}` / `{row['track']}` -> `{row['status']}` "
                f"(dominant_share={row['dominant_share']}, unique={row['unique_predicted_classes']})"
            )
    else:
        lines.append("- No near-constant predictions detected on test rows.")

    lines.extend(
        [
            "",
            "## Subject-level Coverage",
            "",
            f"- Per-subject rows: `{len(per_subject_rows)}`",
            "- The ablation matrix is claim-grade only if the anti-collapse gate remains green for all tracked targets.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_m7_4_runtime_candidate_report(payload: dict[str, Any]) -> str:
    lines = [
        "# M7.4 Runtime Candidate Gate",
        "",
        "## Summary",
        "",
        f"- `experiment_id`: `{payload['experiment_id']}`",
        f"- `source_experiment_id`: `{payload.get('source_experiment_id')}`",
        f"- Gate verdict: `{payload['gate_verdict']}`",
        f"- Gate passed: `{payload['gate_passed']}`",
        "",
        "## Track Winners",
        "",
        "| Track | Winner | macro_f1 | claim | anti-collapse |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload.get("track_winners", []):
        value = row.get("value")
        value_text = f"{float(value):.6f}" if value is not None else "n/a"
        lines.append(
            f"| {row.get('track')} | {row.get('variant_name')} | {value_text} | "
            f"{row.get('claim_status')} | {row.get('anti_collapse_status')} |"
        )

    track_failures = payload.get("track_failures", [])
    if track_failures:
        lines.extend(["", "## Track Failures", ""])
        for item in track_failures:
            lines.append(f"- `{item.get('track')}`: {', '.join(item.get('issues', []))}")

    global_issues = payload.get("global_issues", [])
    if global_issues:
        lines.extend(["", "## Global Issues", ""])
        for issue in global_issues:
            lines.append(f"- `{issue}`")

    remediation_actions = payload.get("remediation_actions", [])
    if remediation_actions:
        lines.extend(["", "## Remediation Actions", ""])
        for item in remediation_actions:
            summary = item.get("action", "action")
            if item.get("variant_name") and item.get("track"):
                summary += f" ({item['variant_name']}/{item['track']})"
            lines.append(f"- {summary}")

    lines.extend(
        [
            "",
            f"- Next if pass: `{payload.get('next_step_if_pass')}`",
            f"- Next if fail: `{payload.get('next_step_if_fail')}`",
            "",
        ]
    )
    return "\n".join(lines)


def _generate_m7_3_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    variant_results: list[PolarFirstVariantResult],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate M7.3 plots") from exc

    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        rows = [row for row in comparison_rows if row["track"] == track_name]
        title = f"M7.3 {track_name.replace('_', ' ').title()} Macro F1 by Ablation"
        _plot_ranked_metric_bars(
            plt=plt,
            rows=rows,
            title=title,
            filename=plots_dir / f"m7-3-{track_name}-macro-f1.png",
        )
        _plot_ranked_delta_bars(
            plt=plt,
            rows=rows,
            title=f"M7.3 {track_name.replace('_', ' ').title()} Delta vs Polar Only",
            filename=plots_dir / f"m7-3-{track_name}-delta-vs-polar-only.png",
        )

    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="activity",
        filename=plots_dir / "m7-3-subject-activity-macro-f1.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="arousal_coarse",
        filename=plots_dir / "m7-3-subject-arousal-macro-f1.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="valence_coarse",
        filename=plots_dir / "m7-3-subject-valence-macro-f1.png",
    )

    best_activity = max(variant_results, key=lambda item: item.tracks["activity"]["test"]["macro_f1"])
    best_arousal = max(variant_results, key=lambda item: item.tracks["arousal_coarse"]["test"]["macro_f1"])
    best_valence = max(variant_results, key=lambda item: item.tracks["valence_coarse"]["test"]["macro_f1"])
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_activity.tracks["activity"]["test"],
        title=f"M7.3 Activity Confusion Matrix ({best_activity.variant_name})",
        filename=plots_dir / "m7-3-activity-confusion-matrix.png",
    )
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_arousal.tracks["arousal_coarse"]["test"],
        title=f"M7.3 Arousal Confusion Matrix ({best_arousal.variant_name})",
        filename=plots_dir / "m7-3-arousal-confusion-matrix.png",
    )
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_valence.tracks["valence_coarse"]["test"],
        title=f"M7.3 Valence Confusion Matrix ({best_valence.variant_name})",
        filename=plots_dir / "m7-3-valence-confusion-matrix.png",
    )


def _generate_m7_9_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    variant_results: list[PolarFirstVariantResult],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate M7.9 plots") from exc

    for track_name in ("activity", "arousal_coarse", "valence_coarse"):
        rows = [row for row in comparison_rows if row["track"] == track_name]
        title = f"M7.9 {track_name.replace('_', ' ').title()} Macro F1 by Ablation"
        _plot_ranked_metric_bars(
            plt=plt,
            rows=rows,
            title=title,
            filename=plots_dir / f"m7-9-{track_name}-macro-f1.png",
        )
        _plot_ranked_delta_bars(
            plt=plt,
            rows=rows,
            title=f"M7.9 {track_name.replace('_', ' ').title()} Delta vs Polar Cardio Only",
            filename=plots_dir / f"m7-9-{track_name}-delta-vs-polar-cardio-only.png",
        )

    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="activity",
        filename=plots_dir / "m7-9-subject-activity-macro-f1.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="arousal_coarse",
        filename=plots_dir / "m7-9-subject-arousal-macro-f1.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="valence_coarse",
        filename=plots_dir / "m7-9-subject-valence-macro-f1.png",
    )

    best_activity = max(variant_results, key=lambda item: item.tracks["activity"]["test"]["macro_f1"])
    best_arousal = max(variant_results, key=lambda item: item.tracks["arousal_coarse"]["test"]["macro_f1"])
    best_valence = max(variant_results, key=lambda item: item.tracks["valence_coarse"]["test"]["macro_f1"])
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_activity.tracks["activity"]["test"],
        title=f"M7.9 Activity Confusion Matrix ({best_activity.variant_name})",
        filename=plots_dir / "m7-9-activity-confusion-matrix.png",
    )
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_arousal.tracks["arousal_coarse"]["test"],
        title=f"M7.9 Arousal Confusion Matrix ({best_arousal.variant_name})",
        filename=plots_dir / "m7-9-arousal-confusion-matrix.png",
    )
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_valence.tracks["valence_coarse"]["test"],
        title=f"M7.9 Valence Confusion Matrix ({best_valence.variant_name})",
        filename=plots_dir / "m7-9-valence-confusion-matrix.png",
    )


def _generate_e2_3_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    variant_results: list[dict[str, Any]],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return

    arousal_rows = [row for row in comparison_rows if row["track"] == "arousal_coarse"]
    valence_rows = [row for row in comparison_rows if row["track"] == "valence_coarse"]
    _plot_metric_bars(
        plt=plt,
        rows=arousal_rows,
        title="E2.3 Arousal Macro F1 by Variant",
        filename=plots_dir / "e2-3-arousal-macro-f1.png",
    )
    _plot_metric_bars(
        plt=plt,
        rows=valence_rows,
        title="E2.3 Valence Macro F1 by Variant",
        filename=plots_dir / "e2-3-valence-macro-f1.png",
    )
    _plot_delta_bars(
        plt=plt,
        rows=arousal_rows,
        title="E2.3 Arousal Delta vs Polar RR Only",
        filename=plots_dir / "e2-3-arousal-delta-vs-polar-rr-only.png",
    )
    _plot_delta_bars(
        plt=plt,
        rows=valence_rows,
        title="E2.3 Valence Delta vs Polar RR Only",
        filename=plots_dir / "e2-3-valence-delta-vs-polar-rr-only.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="arousal_coarse",
        filename=plots_dir / "e2-3-subject-arousal-macro-f1.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="valence_coarse",
        filename=plots_dir / "e2-3-subject-valence-macro-f1.png",
    )

    best_arousal_name = max(arousal_rows, key=lambda item: float(item["value"]))["variant_name"] if arousal_rows else None
    best_valence_name = max(valence_rows, key=lambda item: float(item["value"]))["variant_name"] if valence_rows else None
    if best_arousal_name:
        best = next(item for item in variant_results if item["variant_name"] == best_arousal_name)
        _plot_confusion_matrix(
            plt=plt,
            metrics=best["tracks"]["arousal_coarse"]["test"],
            title=f"E2.3 Arousal Confusion Matrix ({best_arousal_name})",
            filename=plots_dir / "e2-3-arousal-confusion-matrix.png",
        )
    if best_valence_name:
        best = next(item for item in variant_results if item["variant_name"] == best_valence_name)
        _plot_confusion_matrix(
            plt=plt,
            metrics=best["tracks"]["valence_coarse"]["test"],
            title=f"E2.3 Valence Confusion Matrix ({best_valence_name})",
            filename=plots_dir / "e2-3-valence-confusion-matrix.png",
        )


def _build_model_comparison_rows(
    variant_results: list[VariantRunResult],
    test_examples: list[SegmentExample],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    watch_ref = next(item for item in variant_results if item.variant_name == "watch_only_centroid")
    for result in variant_results:
        for track_name, target_field, ref_predicted, predicted in (
            (
                "activity",
                "activity_label",
                watch_ref.activity_test_pred,
                result.activity_test_pred,
            ),
            (
                "arousal_coarse",
                "arousal_coarse",
                watch_ref.arousal_test_pred,
                result.arousal_test_pred,
            ),
        ):
            track = result.tracks[track_name]
            baseline_track = watch_ref.tracks[track_name]
            delta_ci = _bootstrap_pairwise_delta_ci(
                examples=test_examples,
                predicted_a=predicted,
                predicted_b=ref_predicted,
                target_field=target_field,
            )
            delta_value = round(track["test"]["macro_f1"] - baseline_track["test"]["macro_f1"], 6)
            rows.append(
                {
                    "variant_name": result.variant_name,
                    "track": track_name,
                    "metric_name": "macro_f1",
                    "split": "test",
                    "value": track["test"]["macro_f1"],
                    "baseline_name": "watch_only_centroid",
                    "baseline_value": baseline_track["test"]["macro_f1"],
                    "delta_vs_watch_only": delta_value,
                    "delta_vs_watch_only_ci95_low": delta_ci[0],
                    "delta_vs_watch_only_ci95_high": delta_ci[1],
                    "claim_status": _claim_status_from_delta(delta_value=delta_value, delta_ci=delta_ci),
                    "delta_vs_majority": track["delta_vs_majority_macro_f1"],
                    "ci95_low": track["uncertainty"]["primary_metric_ci95"][0],
                    "ci95_high": track["uncertainty"]["primary_metric_ci95"][1],
                }
            )
    return rows


def _build_extended_model_zoo_variants() -> list[VariantSpec]:
    watch_modalities = ("watch_acc", "watch_bvp", "watch_eda", "watch_temp")
    chest_modalities = ("chest_acc", "chest_ecg", "chest_eda", "chest_emg", "chest_resp", "chest_temp")
    fusion_modalities = watch_modalities + chest_modalities

    variants = [
        VariantSpec(
            variant_name="watch_only_centroid",
            model_family="nearest_centroid_feature_baseline",
            classifier_kind="centroid",
            feature_prefixes=("watch_",),
            input_modalities=watch_modalities,
            description="Nearest-centroid wrist-only baseline carried forward from G1/G2.",
            modality_group="watch_only",
            hyperparameters={"distance": "euclidean", "standardize": True},
        ),
        VariantSpec(
            variant_name="chest_only_centroid",
            model_family="nearest_centroid_feature_baseline",
            classifier_kind="centroid",
            feature_prefixes=("chest_",),
            input_modalities=chest_modalities,
            description="Nearest-centroid chest-only reference baseline.",
            modality_group="chest_only",
            hyperparameters={"distance": "euclidean", "standardize": True},
        ),
        VariantSpec(
            variant_name="fusion_centroid",
            model_family="nearest_centroid_feature_baseline",
            classifier_kind="centroid",
            feature_prefixes=("watch_", "chest_"),
            input_modalities=fusion_modalities,
            description="Nearest-centroid fusion reference baseline.",
            modality_group="fusion",
            hyperparameters={"distance": "euclidean", "standardize": True},
        ),
        VariantSpec(
            variant_name="chest_only_gaussian_nb",
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind="gaussian_nb",
            feature_prefixes=("chest_",),
            input_modalities=chest_modalities,
            description="Gaussian naive Bayes chest-only reference baseline.",
            modality_group="chest_only",
            hyperparameters={"var_smoothing": 1e-9},
        ),
    ]

    extended_kinds = [
        "gaussian_nb",
        "logistic_regression",
        "ridge_classifier",
        "lda",
        "qda",
        "linear_svm",
        "rbf_svm",
        "knn",
        "decision_tree",
        "random_forest",
        "extra_trees",
        "bagging_tree",
        "ada_boost",
        "gradient_boosting",
        "hist_gradient_boosting",
        "mlp",
        "sgd_linear",
        "xgboost",
        "lightgbm",
        "catboost",
    ]
    for modality_group, prefixes, input_modalities in (
        ("watch_only", ("watch_",), watch_modalities),
        ("fusion", ("watch_", "chest_"), fusion_modalities),
    ):
        for classifier_kind in extended_kinds:
            if modality_group == "watch_only" and classifier_kind in {"xgboost", "lightgbm", "catboost"}:
                # Keep the heavier boosting families on fusion first to limit redundant runs.
                continue
            variants.append(
                _build_variant_spec(
                    modality_group=modality_group,
                    classifier_kind=classifier_kind,
                    feature_prefixes=prefixes,
                    input_modalities=input_modalities,
                )
            )
    return variants


def _build_variant_spec(
    modality_group: str,
    classifier_kind: str,
    feature_prefixes: tuple[str, ...],
    input_modalities: tuple[str, ...],
) -> VariantSpec:
    variant_name = f"{modality_group}_{classifier_kind}"
    if classifier_kind == "gaussian_nb":
        return VariantSpec(
            variant_name=variant_name,
            model_family="gaussian_naive_bayes_feature_baseline",
            classifier_kind=classifier_kind,
            feature_prefixes=feature_prefixes,
            input_modalities=input_modalities,
            description=f"Gaussian naive Bayes {modality_group.replace('_', '-')} benchmark.",
            modality_group=modality_group,
            hyperparameters={"var_smoothing": 1e-9},
        )

    config = get_classifier_config(classifier_kind)
    return VariantSpec(
        variant_name=variant_name,
        model_family=config.model_family,
        classifier_kind=classifier_kind,
        feature_prefixes=feature_prefixes,
        input_modalities=input_modalities,
        description=f"{config.description} Modality scope: {modality_group.replace('_', '-')}.",
        modality_group=modality_group,
        hyperparameters=config.hyperparameters,
    )


def _build_extended_model_comparison_rows(
    variant_results: list[VariantRunResult],
    test_examples: list[SegmentExample],
    global_baseline_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_name = {item.variant_name: item for item in variant_results}
    global_baseline = by_name[global_baseline_name]
    modality_reference_by_group = {
        result.modality_group: result
        for result in variant_results
        if result.variant_name.endswith("_centroid")
    }

    for result in variant_results:
        modality_reference = modality_reference_by_group.get(result.modality_group, global_baseline)
        for track_name, target_field, global_predicted, predicted, modality_predicted in (
            (
                "activity",
                "activity_label",
                global_baseline.activity_test_pred,
                result.activity_test_pred,
                modality_reference.activity_test_pred,
            ),
            (
                "arousal_coarse",
                "arousal_coarse",
                global_baseline.arousal_test_pred,
                result.arousal_test_pred,
                modality_reference.arousal_test_pred,
            ),
        ):
            track = result.tracks[track_name]
            global_track = global_baseline.tracks[track_name]
            modality_track = modality_reference.tracks[track_name]
            global_delta_ci = _bootstrap_pairwise_delta_ci(
                examples=test_examples,
                predicted_a=predicted,
                predicted_b=global_predicted,
                target_field=target_field,
            )
            modality_delta_ci = _bootstrap_pairwise_delta_ci(
                examples=test_examples,
                predicted_a=predicted,
                predicted_b=modality_predicted,
                target_field=target_field,
            )
            delta_vs_global = round(track["test"]["macro_f1"] - global_track["test"]["macro_f1"], 6)
            delta_vs_modality = round(track["test"]["macro_f1"] - modality_track["test"]["macro_f1"], 6)
            rows.append(
                {
                    "variant_name": result.variant_name,
                    "model_family": result.model_family,
                    "classifier_kind": result.classifier_kind,
                    "modality_group": result.modality_group,
                    "feature_count": len(result.feature_names),
                    "track": track_name,
                    "metric_name": "macro_f1",
                    "split": "test",
                    "value": track["test"]["macro_f1"],
                    "baseline_name": global_baseline.variant_name,
                    "baseline_value": global_track["test"]["macro_f1"],
                    "delta_vs_watch_only": delta_vs_global,
                    "delta_vs_watch_only_ci95_low": global_delta_ci[0],
                    "delta_vs_watch_only_ci95_high": global_delta_ci[1],
                    "claim_status": _claim_status_from_delta(delta_value=delta_vs_global, delta_ci=global_delta_ci),
                    "modality_reference_name": modality_reference.variant_name,
                    "modality_reference_value": modality_track["test"]["macro_f1"],
                    "delta_vs_modality_reference": delta_vs_modality,
                    "delta_vs_modality_reference_ci95_low": modality_delta_ci[0],
                    "delta_vs_modality_reference_ci95_high": modality_delta_ci[1],
                    "modality_claim_status": _claim_status_from_delta(
                        delta_value=delta_vs_modality,
                        delta_ci=modality_delta_ci,
                    ),
                    "delta_vs_majority": track["delta_vs_majority_macro_f1"],
                    "ci95_low": track["uncertainty"]["primary_metric_ci95"][0],
                    "ci95_high": track["uncertainty"]["primary_metric_ci95"][1],
                }
            )
    return rows


def _loso_fold_examples(
    examples: list[SegmentExample],
    test_subject_id: str,
    validation_subject_id: str,
) -> list[SegmentExample]:
    if test_subject_id == validation_subject_id:
        raise ValueError("test_subject_id and validation_subject_id must be different")

    rows: list[SegmentExample] = []
    for item in examples:
        if item.subject_id == test_subject_id:
            split = "test"
        elif item.subject_id == validation_subject_id:
            split = "validation"
        else:
            split = "train"
        rows.append(
            SegmentExample(
                dataset_id=item.dataset_id,
                dataset_version=item.dataset_version,
                subject_id=item.subject_id,
                session_id=item.session_id,
                segment_id=item.segment_id,
                split=split,
                activity_label=item.activity_label,
                arousal_score=item.arousal_score,
                arousal_coarse=item.arousal_coarse,
                valence_score=item.valence_score,
                valence_coarse=item.valence_coarse,
                source_label_value=item.source_label_value,
                features=item.features,
            )
        )
    return rows


def _build_loso_model_comparison_rows(
    variant_fold_scores: dict[tuple[str, str], list[tuple[int, float]]],
    variant_meta: dict[str, dict[str, Any]],
    expected_fold_count: int,
    baseline_variant_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track_name in ("activity", "arousal_coarse"):
        baseline_payload = variant_fold_scores.get((baseline_variant_name, track_name), [])
        baseline_map = {fold_id: value for fold_id, value in baseline_payload}
        if len(baseline_map) != expected_fold_count:
            raise RuntimeError(f"baseline {baseline_variant_name}:{track_name} missing folds for LOSO aggregation")
        baseline_values = [baseline_map[fold_id] for fold_id in sorted(baseline_map.keys())]
        baseline_mean = round(float(np.mean(np.asarray(baseline_values, dtype=float))), 6)

        for (variant_name, row_track), fold_payload in sorted(variant_fold_scores.items()):
            if row_track != track_name:
                continue
            fold_map = {fold_id: value for fold_id, value in fold_payload}
            if len(fold_map) != expected_fold_count:
                continue

            fold_ids = sorted(fold_map.keys())
            values = np.asarray([fold_map[fold_id] for fold_id in fold_ids], dtype=float)
            mean_value = float(np.mean(values))
            std_value = float(np.std(values))
            if values.size > 1:
                ci_delta = 1.96 * (std_value / math.sqrt(float(values.size)))
                ci_low = max(0.0, mean_value - ci_delta)
                ci_high = min(1.0, mean_value + ci_delta)
            else:
                ci_low = mean_value
                ci_high = mean_value

            baseline_fold_values = np.asarray([baseline_map[fold_id] for fold_id in fold_ids], dtype=float)
            delta_values = values - baseline_fold_values
            delta_mean = float(np.mean(delta_values))
            if delta_values.size > 1:
                delta_ci = [
                    round(float(np.percentile(delta_values, 2.5)), 6),
                    round(float(np.percentile(delta_values, 97.5)), 6),
                ]
            else:
                delta_ci = [round(delta_mean, 6), round(delta_mean, 6)]

            meta = variant_meta[variant_name]
            rows.append(
                {
                    "variant_name": variant_name,
                    "model_family": meta["model_family"],
                    "classifier_kind": meta["classifier_kind"],
                    "modality_group": meta["modality_group"],
                    "feature_count": meta["feature_count"],
                    "track": track_name,
                    "metric_name": "macro_f1",
                    "evaluation_mode": "loso",
                    "fold_count": expected_fold_count,
                    "mean_macro_f1": round(mean_value, 6),
                    "std_macro_f1": round(std_value, 6),
                    "ci95_low": round(ci_low, 6),
                    "ci95_high": round(ci_high, 6),
                    "baseline_name": baseline_variant_name,
                    "baseline_mean_macro_f1": baseline_mean,
                    "delta_vs_watch_only": round(delta_mean, 6),
                    "delta_vs_watch_only_ci95_low": delta_ci[0],
                    "delta_vs_watch_only_ci95_high": delta_ci[1],
                    "claim_status": _claim_status_from_delta(delta_value=delta_mean, delta_ci=delta_ci),
                }
            )
    return rows


def _extended_prediction_rows(
    examples: list[SegmentExample],
    variant_results: list[VariantRunResult],
) -> list[dict[str, Any]]:
    test_examples = [item for item in examples if item.split == "test"]
    rows: list[dict[str, Any]] = []
    for result in variant_results:
        for row in _prediction_rows(
            variant_name=result.variant_name,
            model_family=result.model_family,
            examples=test_examples,
            activity_pred=result.activity_test_pred,
            arousal_pred=result.arousal_test_pred,
            arousal_score_pred=result.arousal_test_score_pred,
        ):
            row["classifier_kind"] = result.classifier_kind
            row["modality_group"] = result.modality_group
            rows.append(row)
    return rows


def _extended_per_subject_rows(variant_results: list[VariantRunResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in variant_results:
        for row in result.per_subject_rows:
            rows.append(
                {
                    "variant_name": result.variant_name,
                    "model_family": result.model_family,
                    "classifier_kind": result.classifier_kind,
                    "modality_group": result.modality_group,
                    "track": row["track"],
                    "subject_id": row["subject_id"],
                    "macro_f1": row["macro_f1"],
                    "balanced_accuracy": row["balanced_accuracy"],
                    "support": row["support"],
                }
            )
    return rows


def _load_previous_g3_reference(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    report = _load_json(path)
    winners = report.get("winner_by_track", {})
    if not winners:
        return None
    return {
        "experiment_id": report.get("experiment_id"),
        "winner_by_track": winners,
    }


def _build_fusion_report(
    experiment_id: str,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    split_manifest: dict[str, Any],
    labels: list[dict[str, Any]],
    min_confidence: float,
    variants: list[VariantSpec],
    variant_results: list[VariantRunResult],
    comparison_rows: list[dict[str, Any]],
    generated_at: datetime,
) -> dict[str, Any]:
    winners = {}
    for track_name in ("activity", "arousal_coarse"):
        ordered = sorted(
            comparison_rows,
            key=lambda item: (item["track"] == track_name, item["value"]),
        )
        track_rows = [row for row in comparison_rows if row["track"] == track_name]
        best = max(track_rows, key=lambda item: item["value"])
        winners[track_name] = {
            "variant_name": best["variant_name"],
            "metric_name": best["metric_name"],
            "value": best["value"],
            "delta_vs_watch_only": best["delta_vs_watch_only"],
        }

    return {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "comparison_goal": "Compare watch-only, chest-only and fusion baselines under the same WESAD subject-wise split.",
        "variants": [
            {
                "variant_name": variant.variant_name,
                "model_family": variant.model_family,
                "classifier_kind": variant.classifier_kind,
                "input_modalities": list(variant.input_modalities),
                "feature_count": len(result.feature_names),
                "description": variant.description,
                "tracks": result.tracks,
                "splits": result.splits,
            }
            for variant, result in zip(variants, variant_results)
        ],
        "comparison_summary": {
            "winner_by_track": winners,
            "model_comparison": comparison_rows,
        },
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "evaluation_subset": "wesad unified segment labels with confidence >= min_confidence on subject-wise split manifest",
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "generated_at_utc": generated_at.isoformat(),
    }


def _build_model_zoo_report(
    experiment_id: str,
    dataset_id: str,
    dataset_version: str,
    preprocessing_version: str,
    split_manifest: dict[str, Any],
    labels: list[dict[str, Any]],
    min_confidence: float,
    variants: list[VariantSpec],
    variant_results: list[VariantRunResult],
    failed_variants: list[FailedVariantRun],
    comparison_rows: list[dict[str, Any]],
    previous_reference: dict[str, Any] | None,
    generated_at: datetime,
    examples: list[SegmentExample],
) -> dict[str, Any]:
    winners_by_track = {}
    winners_by_track_and_modality = {}
    for track_name in ("activity", "arousal_coarse"):
        track_rows = [row for row in comparison_rows if row["track"] == track_name]
        best = max(track_rows, key=lambda item: float(item["value"]))
        winners_by_track[track_name] = {
            "variant_name": best["variant_name"],
            "model_family": best["model_family"],
            "classifier_kind": best["classifier_kind"],
            "modality_group": best["modality_group"],
            "value": best["value"],
            "claim_status": best["claim_status"],
            "delta_vs_watch_only": best["delta_vs_watch_only"],
            "delta_vs_modality_reference": best["delta_vs_modality_reference"],
        }
        modality_winners = {}
        for modality_group in sorted({row["modality_group"] for row in track_rows}):
            modality_rows = [row for row in track_rows if row["modality_group"] == modality_group]
            winner = max(modality_rows, key=lambda item: float(item["value"]))
            modality_winners[modality_group] = {
                "variant_name": winner["variant_name"],
                "model_family": winner["model_family"],
                "classifier_kind": winner["classifier_kind"],
                "value": winner["value"],
                "claim_status": winner["claim_status"],
                "delta_vs_watch_only": winner["delta_vs_watch_only"],
                "delta_vs_modality_reference": winner["delta_vs_modality_reference"],
            }
        winners_by_track_and_modality[track_name] = modality_winners

    previous_best_delta = None
    if previous_reference is not None:
        previous_best_delta = {}
        for track_name, winner in winners_by_track.items():
            previous_winner = previous_reference["winner_by_track"].get(track_name)
            if previous_winner is None:
                continue
            previous_best_delta[track_name] = {
                "previous_experiment_id": previous_reference["experiment_id"],
                "previous_variant_name": previous_winner["variant_name"],
                "previous_value": previous_winner["value"],
                "delta": round(float(winner["value"]) - float(previous_winner["value"]), 6),
            }

    status = "baseline"
    if previous_best_delta:
        deltas = [float(item["delta"]) for item in previous_best_delta.values()]
        if all(delta > 0.0 for delta in deltas):
            status = "improved"
        elif any(delta < 0.0 for delta in deltas):
            status = "mixed"
        else:
            status = "inconclusive"

    attempted_variants = [
        {
            "variant_name": variant.variant_name,
            "model_family": variant.model_family,
            "classifier_kind": variant.classifier_kind,
            "modality_group": variant.modality_group,
            "input_modalities": list(variant.input_modalities),
            "hyperparameters": variant.hyperparameters or {},
            "description": variant.description,
        }
        for variant in variants
    ]
    completed_variants = [
        {
            "variant_name": result.variant_name,
            "model_family": result.model_family,
            "classifier_kind": result.classifier_kind,
            "modality_group": result.modality_group,
            "input_modalities": result.input_modalities,
            "feature_count": len(result.feature_names),
            "tracks": result.tracks,
            "splits": result.splits,
        }
        for result in variant_results
    ]
    failed_variant_rows = [
        {
            "variant_name": row.variant_name,
            "model_family": row.model_family,
            "classifier_kind": row.classifier_kind,
            "modality_group": row.modality_group,
            "input_modalities": row.input_modalities,
            "error_type": row.error_type,
            "error_message": row.error_message,
        }
        for row in failed_variants
    ]

    unique_subjects = len({item.subject_id for item in examples})
    unique_sessions = len({item.session_id for item in examples})
    split_summaries = {
        "train": _split_summary([item for item in examples if item.split == "train"]),
        "validation": _split_summary([item for item in examples if item.split == "validation"]),
        "test": _split_summary([item for item in examples if item.split == "test"]),
    }

    return {
        "experiment_id": experiment_id,
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "comparison_goal": "Benchmark a broad model zoo across watch-only, chest reference and fusion feature sets under the same WESAD split.",
        "research_hypothesis": "Broader classical and boosting model families should outperform the narrow G1-G3 baselines and clarify which modality/model combinations are most suitable before personalization.",
        "status": status,
        "attempted_variants": attempted_variants,
        "completed_variants": completed_variants,
        "failed_variants": failed_variant_rows,
        "comparison_summary": {
            "winner_by_track": winners_by_track,
            "winner_by_track_and_modality": winners_by_track_and_modality,
            "model_comparison": comparison_rows,
            "previous_best_delta": previous_best_delta,
        },
        "data_provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "evaluation_subset": "wesad unified segment labels with confidence >= min_confidence on subject-wise split manifest",
            "subjects": unique_subjects,
            "sessions": unique_sessions,
            "segments": len(examples),
            "split_summaries": split_summaries,
            "exclusions": _exclusion_summary(labels, min_confidence=min_confidence),
        },
        "label_definition": {
            "targets": ["activity_label", "arousal_coarse", "arousal_ordinal"],
            "source_artifact": "unified/segment-labels.jsonl",
            "coarse_mapping": {"low": "1..3", "medium": "4..6", "high": "7..9"},
            "min_confidence": min_confidence,
        },
        "preprocessing": {
            "stream_sources": ["watch:ACC", "watch:BVP", "watch:EDA", "watch:TEMP", "chest:ACC", "chest:ECG", "chest:EDA", "chest:EMG", "chest:Resp", "chest:Temp"],
            "windowing": "segment-aligned raw WESAD protocol segments",
            "feature_families": ["channel mean", "channel std", "channel min", "channel max", "channel last", "accelerometer magnitude summaries"],
            "leakage_guards": [
                "subject-wise split manifest",
                "feature extraction only from raw signal windows inside labeled segment boundaries",
                "train-only standardization inside model wrappers when enabled",
            ],
        },
        "generated_at_utc": generated_at.isoformat(),
    }


def _write_per_subject_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["variant_name", "track", "subject_id", "macro_f1", "balanced_accuracy", "support"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "track",
                "metric_name",
                "split",
                "value",
                "baseline_name",
                "baseline_value",
                "delta_vs_watch_only",
                "delta_vs_watch_only_ci95_low",
                "delta_vs_watch_only_ci95_high",
                "claim_status",
                "delta_vs_majority",
                "ci95_low",
                "ci95_high",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_m7_3_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "track",
                "metric_name",
                "split",
                "value",
                "baseline_name",
                "baseline_value",
                "delta_vs_polar_only",
                "delta_vs_polar_only_ci95_low",
                "delta_vs_polar_only_ci95_high",
                "delta_vs_watch_only",
                "delta_vs_watch_only_ci95_low",
                "delta_vs_watch_only_ci95_high",
                "claim_status",
                "delta_vs_majority",
                "ci95_low",
                "ci95_high",
                "anti_collapse_status",
                "anti_collapse_unique_predicted_classes",
                "anti_collapse_dominant_share",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_extended_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "subject_id",
                "session_id",
                "segment_id",
                "source_label_value",
                "activity_true",
                "activity_pred",
                "arousal_coarse_true",
                "arousal_coarse_pred",
                "arousal_score_true",
                "arousal_score_pred",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_extended_per_subject_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "track",
                "subject_id",
                "macro_f1",
                "balanced_accuracy",
                "support",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_extended_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "feature_count",
                "track",
                "metric_name",
                "split",
                "value",
                "baseline_name",
                "baseline_value",
                "delta_vs_watch_only",
                "delta_vs_watch_only_ci95_low",
                "delta_vs_watch_only_ci95_high",
                "claim_status",
                "modality_reference_name",
                "modality_reference_value",
                "delta_vs_modality_reference",
                "delta_vs_modality_reference_ci95_low",
                "delta_vs_modality_reference_ci95_high",
                "modality_claim_status",
                "delta_vs_majority",
                "ci95_low",
                "ci95_high",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_feature_importance_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "track",
                "feature_name",
                "importance",
                "importance_abs",
                "importance_kind",
                "rank",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_failed_variants_csv(path: Path, rows: list[FailedVariantRun]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "input_modalities",
                "error_type",
                "error_message",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "variant_name": row.variant_name,
                    "model_family": row.model_family,
                    "classifier_kind": row.classifier_kind,
                    "modality_group": row.modality_group,
                    "input_modalities": ",".join(row.input_modalities),
                    "error_type": row.error_type,
                    "error_message": row.error_message,
                }
                for row in rows
            ]
        )


def _write_h2_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "subject_id",
                "session_id",
                "segment_id",
                "is_calibration_segment",
                "activity_true",
                "activity_global_pred",
                "activity_personalized_pred",
                "arousal_coarse_true",
                "arousal_coarse_global_pred",
                "arousal_coarse_personalized_pred",
                "arousal_score_true",
                "arousal_score_global_pred",
                "arousal_score_personalized_pred",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h2_per_subject_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "track",
                "subject_id",
                "global_macro_f1",
                "personalized_macro_f1",
                "gain_macro_f1",
                "global_balanced_accuracy",
                "personalized_balanced_accuracy",
                "support",
                "calibration_segments",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_g3_1_loso_fold_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "fold_id",
                "test_subject_id",
                "validation_subject_id",
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "track",
                "metric_name",
                "value",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_g3_1_loso_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "feature_count",
                "track",
                "metric_name",
                "evaluation_mode",
                "fold_count",
                "mean_macro_f1",
                "std_macro_f1",
                "ci95_low",
                "ci95_high",
                "baseline_name",
                "baseline_mean_macro_f1",
                "delta_vs_watch_only",
                "delta_vs_watch_only_ci95_low",
                "delta_vs_watch_only_ci95_high",
                "claim_status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h2_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "track",
                "evaluation_mode",
                "metric_name",
                "split",
                "value",
                "baseline_name",
                "baseline_value",
                "delta_vs_global",
                "claim_status",
                "support",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h3_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "subject_id",
                "session_id",
                "segment_id",
                "activity_true",
                "activity_global_pred",
                "activity_light_pred",
                "activity_full_pred",
                "arousal_coarse_true",
                "arousal_coarse_global_pred",
                "arousal_coarse_light_pred",
                "arousal_coarse_full_pred",
                "arousal_score_true",
                "arousal_score_global_pred",
                "arousal_score_light_pred",
                "arousal_score_full_pred",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h3_per_subject_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "track",
                "subject_id",
                "global_macro_f1",
                "light_macro_f1",
                "full_macro_f1",
                "gain_light_vs_global",
                "gain_full_vs_global",
                "gain_full_vs_light",
                "support",
                "calibration_segments",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h3_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "track",
                "evaluation_mode",
                "metric_name",
                "split",
                "value",
                "baseline_name",
                "baseline_value",
                "delta_vs_global",
                "delta_vs_light",
                "claim_status",
                "support",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h5_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "subject_id",
                "session_id",
                "segment_id",
                "activity_true",
                "activity_global_pred",
                "activity_weak_label_pred",
                "activity_label_free_pred",
                "arousal_coarse_true",
                "arousal_coarse_global_pred",
                "arousal_coarse_weak_label_pred",
                "arousal_coarse_label_free_pred",
                "arousal_score_true",
                "arousal_score_global_pred",
                "arousal_score_weak_label_pred",
                "arousal_score_label_free_pred",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h5_per_subject_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "track",
                "subject_id",
                "global_macro_f1",
                "weak_label_macro_f1",
                "label_free_macro_f1",
                "gain_weak_label_vs_global",
                "gain_label_free_vs_global",
                "gain_label_free_vs_weak_label",
                "support",
                "calibration_segments",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_h5_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "model_family",
                "classifier_kind",
                "modality_group",
                "track",
                "evaluation_mode",
                "metric_name",
                "split",
                "value",
                "baseline_name",
                "baseline_value",
                "delta_vs_global",
                "delta_vs_weak_label",
                "claim_status",
                "support",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_g3_model_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "source_step",
                "run_id",
                "track",
                "metric_name",
                "split",
                "value",
                "baseline_name",
                "baseline_value",
                "delta_vs_watch_only",
                "delta_vs_watch_only_ci95_low",
                "delta_vs_watch_only_ci95_high",
                "claim_status",
                "delta_vs_majority",
                "ci95_low",
                "ci95_high",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_g3_per_subject_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "variant_name",
                "source_step",
                "run_id",
                "track",
                "subject_id",
                "macro_f1",
                "balanced_accuracy",
                "support",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _g1_comparison_rows(g1_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for track_name in ("activity", "arousal_coarse"):
        track = g1_report["tracks"][track_name]
        rows.append(
            {
                "variant_name": "g1_watch_only_centroid",
                "track": track_name,
                "metric_name": "macro_f1",
                "split": "test",
                "value": track["test"]["macro_f1"],
                "baseline_name": "g1_watch_only_centroid",
                "baseline_value": track["test"]["macro_f1"],
                "delta_vs_watch_only": 0.0,
                "delta_vs_watch_only_ci95_low": 0.0,
                "delta_vs_watch_only_ci95_high": 0.0,
                "claim_status": "inconclusive",
                "delta_vs_majority": track["delta_vs_majority_macro_f1"],
                "ci95_low": track["uncertainty"]["primary_metric_ci95"][0],
                "ci95_high": track["uncertainty"]["primary_metric_ci95"][1],
            }
        )
    return rows


def _g1_per_subject_rows(g1_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for track_name in ("activity", "arousal_coarse"):
        for item in g1_report["tracks"][track_name]["subject_level_breakdown_test"]:
            rows.append(
                {
                    "variant_name": "g1_watch_only_centroid",
                    "track": track_name,
                    "subject_id": item["subject_id"],
                    "macro_f1": item["macro_f1"],
                    "balanced_accuracy": item["balanced_accuracy"],
                    "support": item["support"],
                }
            )
    return rows


def _load_csv_dict_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _build_g3_report_markdown(report: dict[str, Any], g1_report: dict[str, Any], g2_report: dict[str, Any]) -> str:
    activity_rows = [row for row in report["model_comparison"] if row["track"] == "activity"]
    arousal_rows = [row for row in report["model_comparison"] if row["track"] == "arousal_coarse"]
    activity_rows_sorted = sorted(activity_rows, key=lambda item: float(item["value"]), reverse=True)
    arousal_rows_sorted = sorted(arousal_rows, key=lambda item: float(item["value"]), reverse=True)
    lines = [
        "# G3 Comparative Evaluation Report",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Scope: {report['comparison_scope']}",
        f"- Source run `G1`: `{g1_report['experiment_id']}`",
        f"- Source run `G2`: `{g2_report['experiment_id']}`",
        f"- Activity winner: `{report['winner_by_track']['activity']['variant_name']}` (`macro_f1={report['winner_by_track']['activity']['value']}`; claim=`{report['winner_by_track']['activity']['claim_status']}`).",
        f"- Arousal winner: `{report['winner_by_track']['arousal_coarse']['variant_name']}` (`macro_f1={report['winner_by_track']['arousal_coarse']['value']}`; claim=`{report['winner_by_track']['arousal_coarse']['claim_status']}`).",
        "",
        "## Data and Label Provenance",
        "",
        f"- Dataset: `{report['dataset_version']}`",
        f"- Label set: `{report['label_set_version']}`",
        f"- Preprocessing version: `{report['preprocessing_version']}`",
        "- All compared runs use the same subject-wise split strategy from `wesad-v1` artifacts.",
        "",
        "## Model Families and Variants",
        "",
        "- `g1_watch_only_centroid` (`G1`)",
        "- `watch_only_centroid` (`G2`)",
        "- `chest_only_centroid` (`G2`)",
        "- `fusion_centroid` (`G2`)",
        "- `fusion_gaussian_nb` (`G2`)",
        "",
        "## Results: Activity",
        "",
        "| Variant | Step | macro_f1 | delta_vs_watch_only | delta_ci95 | claim |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in activity_rows_sorted:
        lines.append(
            "| "
            f"{row['variant_name']} | {row['source_step']} | {float(row['value']):.6f} | "
            f"{float(row['delta_vs_watch_only']):.6f} | "
            f"[{row['delta_vs_watch_only_ci95_low']}, {row['delta_vs_watch_only_ci95_high']}] | "
            f"{row['claim_status']} |"
        )
    lines.extend(
        [
            "",
            "## Results: Arousal Coarse",
            "",
            "| Variant | Step | macro_f1 | delta_vs_watch_only | delta_ci95 | claim |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in arousal_rows_sorted:
        lines.append(
            "| "
            f"{row['variant_name']} | {row['source_step']} | {float(row['value']):.6f} | "
            f"{float(row['delta_vs_watch_only']):.6f} | "
            f"[{row['delta_vs_watch_only_ci95_low']}, {row['delta_vs_watch_only_ci95_high']}] | "
            f"{row['claim_status']} |"
        )
    lines.extend(
        [
            "",
            "## Failure Analysis",
            "",
            "- Holdout test set still has only 3 subjects; this keeps CI wide on some comparisons.",
            "- `fusion_centroid` underperforms against watch-only; fusion signal does not guarantee gains without suitable model family.",
            "- `fusion_gaussian_nb` demonstrates strong gains, but activity delta CI still touches zero, so activity claim remains inconclusive at this stage.",
            "",
            "## Research Conclusion",
            "",
            "- Strongest evidence in current corpus: fusion improves `arousal_coarse` with claim status `supported` for `fusion_gaussian_nb`.",
            "- For `activity`, current result is promising but not yet claim-level conclusive.",
            "- Next modeling step should focus on richer families and/or larger subject coverage before final research gate.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_research_report_markdown(
    report: dict[str, Any],
    variants: list[VariantSpec],
    variant_results: list[VariantRunResult],
) -> str:
    winner_activity = report["comparison_summary"]["winner_by_track"]["activity"]
    winner_arousal = report["comparison_summary"]["winner_by_track"]["arousal_coarse"]
    winner_activity_row = next(
        row
        for row in report["comparison_summary"]["model_comparison"]
        if row["track"] == "activity" and row["variant_name"] == winner_activity["variant_name"]
    )
    winner_arousal_row = next(
        row
        for row in report["comparison_summary"]["model_comparison"]
        if row["track"] == "arousal_coarse" and row["variant_name"] == winner_arousal["variant_name"]
    )
    lines = [
        "# G2 Fusion Baseline Research Report",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        "- Goal: compare watch-only, chest-only and fusion baselines on the same WESAD subject-wise split.",
        "- Hypothesis: fusion should outperform watch-only on at least one mandatory headline track.",
        f"- Activity winner: `{winner_activity['variant_name']}` with `macro_f1={winner_activity['value']}` and `delta_vs_watch_only={winner_activity['delta_vs_watch_only']}`.",
        f"- Arousal winner: `{winner_arousal['variant_name']}` with `macro_f1={winner_arousal['value']}` and `delta_vs_watch_only={winner_arousal['delta_vs_watch_only']}`.",
        "",
        "## Data Provenance",
        "",
        f"- Dataset: `{report['dataset_version']}`",
        f"- Label set: `{report['label_set_version']}`",
        f"- Preprocessing version: `{report['preprocessing_version']}`",
        f"- Split manifest: `{report['split_manifest_version']}`",
        f"- Exclusions: `{json.dumps(report['data_provenance']['exclusions'], ensure_ascii=False)}`",
        "",
        "## Label Definition and Usage",
        "",
        "- Targets: `activity_label`, `arousal_score -> arousal_coarse`, `arousal_score ordinal`.",
        "- Canonical labels come from `A2-v1` / unified `segment-labels.jsonl`.",
        "- Only segments with `confidence >= 0.7` were retained.",
        "",
        "## Preprocessing and Features",
        "",
        "- Segment boundaries come from unified provenance indices mapped back to WESAD raw streams.",
        "- Wrist feature families: `ACC/BVP/EDA/TEMP` summary statistics.",
        "- Chest feature families: `ACC/ECG/EDA/EMG/Resp/Temp` summary statistics.",
        "- Each channel contributes `mean/std/min/max/last`; accelerometer magnitude is added separately.",
        "",
        "## Compared Models",
        "",
    ]
    for variant, result in zip(variants, variant_results):
        lines.append(
            f"- `{variant.variant_name}`: family=`{variant.model_family}`, modalities=`{','.join(variant.input_modalities)}`, features=`{len(result.feature_names)}`."
        )
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Variant | Activity macro_f1 | Activity delta CI | Arousal macro_f1 | Arousal delta CI | Ordinal QWK |",
            "| --- | ---: | --- | ---: | --- | ---: |",
        ]
    )
    for variant, result in zip(variants, variant_results):
        activity_row = next(
            row
            for row in report["comparison_summary"]["model_comparison"]
            if row["track"] == "activity" and row["variant_name"] == variant.variant_name
        )
        arousal_row = next(
            row
            for row in report["comparison_summary"]["model_comparison"]
            if row["track"] == "arousal_coarse" and row["variant_name"] == variant.variant_name
        )
        lines.append(
            "| "
            f"{variant.variant_name} | "
            f"{result.tracks['activity']['test']['macro_f1']:.6f} | "
            f"[{activity_row['delta_vs_watch_only_ci95_low']}, {activity_row['delta_vs_watch_only_ci95_high']}] | "
            f"{result.tracks['arousal_coarse']['test']['macro_f1']:.6f} | "
            f"[{arousal_row['delta_vs_watch_only_ci95_low']}, {arousal_row['delta_vs_watch_only_ci95_high']}] | "
            f"{result.tracks['arousal_ordinal']['test']['quadratic_weighted_kappa']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Failure Analysis",
            "",
            "- Confusion matrices show the main confusions between `focused_cognitive_task` and `recovery_rest`, and between neighboring arousal classes.",
            "- Subject-level spread remains wide because the holdout set contains only three subjects.",
            "- `feature-importance.csv` is not produced for this step because centroid and Gaussian NB baselines do not expose a stable feature-importance artifact in the current implementation.",
            "",
            "## Research Conclusion",
            "",
            f"- Activity-track best variant: `{winner_activity['variant_name']}` with claim status `{winner_activity_row['claim_status']}`.",
            f"- Arousal-track best variant: `{winner_arousal['variant_name']}` with claim status `{winner_arousal_row['claim_status']}`.",
            "- Result should be treated as a baseline comparison, not a final modality claim, until it is integrated with the broader comparative report in `G3`.",
            "- Next step: aggregate G1 and G2 into a single comparative evaluation package with narrative and cross-run plots.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_model_zoo_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    variant_results: list[VariantRunResult],
    feature_importance_rows: list[dict[str, Any]],
    previous_reference: dict[str, Any] | None,
) -> str:
    winners = report["comparison_summary"]["winner_by_track"]
    previous_deltas = report["comparison_summary"].get("previous_best_delta") or {}
    successful_count = len(variant_results)
    failed_count = len(report["failed_variants"])
    lines = [
        "# G3.1 Extended Model Zoo Benchmark",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Goal: {report['comparison_goal']}",
        f"- Successful variants: `{successful_count}`",
        f"- Failed variants: `{failed_count}`",
        f"- Activity winner: `{winners['activity']['variant_name']}` (`macro_f1={winners['activity']['value']}`, `claim={winners['activity']['claim_status']}`).",
        f"- Arousal winner: `{winners['arousal_coarse']['variant_name']}` (`macro_f1={winners['arousal_coarse']['value']}`, `claim={winners['arousal_coarse']['claim_status']}`).",
    ]
    if previous_reference is not None:
        for track_name in ("activity", "arousal_coarse"):
            delta_block = previous_deltas.get(track_name)
            if delta_block is None:
                continue
            lines.append(
                f"- Delta vs previous best `{track_name}` winner from `{delta_block['previous_experiment_id']}`: `{delta_block['delta']}`."
            )
    lines.extend(
        [
            "",
            "## Data Provenance",
            "",
            f"- Dataset: `{report['dataset_version']}`",
            f"- Label set: `{report['label_set_version']}`",
            f"- Preprocessing version: `{report['preprocessing_version']}`",
            f"- Split manifest: `{report['split_manifest_version']}`",
            f"- Subject/session/segment counts: `{json.dumps(report['data_provenance']['split_summaries'], ensure_ascii=False)}`",
            f"- Exclusions: `{json.dumps(report['data_provenance']['exclusions'], ensure_ascii=False)}`",
            "",
            "## Labels and Preprocessing",
            "",
            "- Targets: `activity_label`, `arousal_coarse`, and ordinal `arousal_score`.",
            "- Coarse mapping: `1..3 -> low`, `4..6 -> medium`, `7..9 -> high`.",
            "- Feature set uses segment-aligned summary statistics over watch and chest raw channels with train-only standardization for applicable model families.",
            "",
            "## Compared Model Families",
            "",
        ]
    )
    for modality_group in ("watch_only", "chest_only", "fusion"):
        modality_rows = [row for row in comparison_rows if row["track"] == "activity" and row["modality_group"] == modality_group]
        if not modality_rows:
            continue
        lines.append(f"### {modality_group}")
        lines.append("")
        for row in sorted(modality_rows, key=lambda item: float(item["value"]), reverse=True):
            lines.append(
                f"- `{row['variant_name']}`: family=`{row['model_family']}`, classifier=`{row['classifier_kind']}`, features=`{row['feature_count']}`."
            )
        lines.append("")

    lines.extend(
        [
            "## Results: Activity",
            "",
            "| Variant | Modality | Family | macro_f1 | delta_vs_watch | delta_vs_modality_ref | claim |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in sorted((item for item in comparison_rows if item["track"] == "activity"), key=lambda item: float(item["value"]), reverse=True)[:15]:
        lines.append(
            "| "
            f"{row['variant_name']} | {row['modality_group']} | {row['classifier_kind']} | "
            f"{float(row['value']):.6f} | {float(row['delta_vs_watch_only']):.6f} | "
            f"{float(row['delta_vs_modality_reference']):.6f} | {row['claim_status']} |"
        )
    lines.extend(
        [
            "",
            "## Results: Arousal Coarse",
            "",
            "| Variant | Modality | Family | macro_f1 | delta_vs_watch | delta_vs_modality_ref | claim |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in sorted((item for item in comparison_rows if item["track"] == "arousal_coarse"), key=lambda item: float(item["value"]), reverse=True)[:15]:
        lines.append(
            "| "
            f"{row['variant_name']} | {row['modality_group']} | {row['classifier_kind']} | "
            f"{float(row['value']):.6f} | {float(row['delta_vs_watch_only']):.6f} | "
            f"{float(row['delta_vs_modality_reference']):.6f} | {row['claim_status']} |"
        )

    top_feature_rows = [row for row in feature_importance_rows if int(row["rank"]) <= 8]
    lines.extend(
        [
            "",
            "## Feature Importance Snapshot",
            "",
        ]
    )
    if top_feature_rows:
        for track_name in ("activity", "arousal_coarse"):
            relevant = [
                row
                for row in top_feature_rows
                if row["track"] == track_name and row["variant_name"] in {winners[track_name]["variant_name"]}
            ]
            if not relevant:
                continue
            lines.append(f"- Top features for `{winners[track_name]['variant_name']}` / `{track_name}`:")
            for row in relevant[:8]:
                lines.append(
                    f"  - `{row['feature_name']}` (`importance_abs={row['importance_abs']}`, kind=`{row['importance_kind']}`)"
                )
    else:
        lines.append("- No feature importance artifact was available for the successful variants in this run.")

    lines.extend(
        [
            "",
            "## Failure Analysis",
            "",
            f"- Failed variants count: `{failed_count}`.",
            "- Holdout test still contains only three subjects, so CI remains wide and ranking gaps between close models should not be over-interpreted.",
            "- Some expressive families can outperform in one track and regress in another; modality-aware review is required before choosing a single production family.",
            "- Chest-only was kept as reference scope, not as the primary optimization target for this step.",
            "",
            "## Research Conclusion",
            "",
            f"- Best overall `activity` model: `{winners['activity']['variant_name']}` (`{winners['activity']['modality_group']}`, `{winners['activity']['classifier_kind']}`).",
            f"- Best overall `arousal_coarse` model: `{winners['arousal_coarse']['variant_name']}` (`{winners['arousal_coarse']['modality_group']}`, `{winners['arousal_coarse']['classifier_kind']}`).",
            "- This step establishes a much broader pre-personalization benchmark and narrows which global families should be carried into H1-H3.",
            "- Next step should return to `H1` and define user profile schema using the strongest global watch-only and fusion candidates from this benchmark.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_g3_1_loso_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# G3.1 Extended Model Zoo Benchmark (LOSO)",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Evaluation mode: `{report['evaluation_mode']}`",
        f"- Fold count: `{report['fold_count']}`",
        f"- Status: `{report['status']}`",
        "",
        "## Winners",
        "",
    ]
    for track_name in ("activity", "arousal_coarse"):
        winner = report["comparison_summary"]["winner_by_track"].get(track_name)
        if winner is None:
            continue
        lines.append(
            f"- `{track_name}`: `{winner['variant_name']}` "
            f"(mean=`{winner['mean_macro_f1']}`, std=`{winner['std_macro_f1']}`, claim=`{winner['claim_status']}`)"
        )

    lines.extend(["", "## Model Comparison (mean macro_f1)", ""])
    for track_name in ("activity", "arousal_coarse"):
        lines.append(f"### {track_name}")
        lines.append("")
        lines.append("| Variant | Modality | mean | std | CI95 | delta_vs_watch | claim |")
        lines.append("| --- | --- | ---: | ---: | --- | ---: | --- |")
        track_rows = sorted(
            [row for row in comparison_rows if row["track"] == track_name],
            key=lambda item: float(item["mean_macro_f1"]),
            reverse=True,
        )
        for row in track_rows[:15]:
            lines.append(
                f"| {row['variant_name']} | {row['modality_group']} | {float(row['mean_macro_f1']):.6f} | "
                f"{float(row['std_macro_f1']):.6f} | "
                f"[{float(row['ci95_low']):.6f}, {float(row['ci95_high']):.6f}] | "
                f"{float(row['delta_vs_watch_only']):.6f} | {row['claim_status']} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- LOSO ranking should be used as primary model-selection view for small-subject corpora.",
            "- Fixed-holdout results can be kept only as supplementary debugging evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_h2_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
) -> str:
    winners = report["comparison_summary"]["winner_by_track"]
    lines = [
        "# H2 Light Personalization Comparative Report",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Goal: {report['comparison_goal']}",
        f"- Calibration policy: `{report['calibration_policy']['adaptation_method']}`",
        f"- Calibration segments per subject: `{report['calibration_policy']['calibration_segments_per_subject']}`",
        f"- Activity winner: `{winners['activity']['variant_name']}` (`macro_f1={winners['activity']['value']}`, `delta_vs_global={winners['activity']['delta_vs_global']}`).",
        f"- Arousal winner: `{winners['arousal_coarse']['variant_name']}` (`macro_f1={winners['arousal_coarse']['value']}`, `delta_vs_global={winners['arousal_coarse']['delta_vs_global']}`).",
        "",
        "## Data Provenance",
        "",
        f"- Dataset: `{report['dataset_version']}`",
        f"- Label set: `{report['label_set_version']}`",
        f"- Preprocessing version: `{report['preprocessing_version']}`",
        f"- Split manifest: `{report['split_manifest_version']}`",
        f"- Exclusions: `{json.dumps(report['data_provenance']['exclusions'], ensure_ascii=False)}`",
        "",
        "## Compared Variants",
        "",
    ]
    for item in report["variants"]:
        lines.append(
            f"- `{item['variant_name']}` (`{item['modality_group']}`, `{item['classifier_kind']}`), "
            f"features=`{item['feature_count']}`, eval subjects after calibration=`{item['split_summary']['eval_subjects_after_calibration']}`."
        )

    lines.extend(
        [
            "",
            "## Results: Global vs Light Personalization",
            "",
            "| Variant | Track | Mode | macro_f1 | delta_vs_global | claim |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in sorted(comparison_rows, key=lambda item: (item["track"], item["variant_name"], item["evaluation_mode"])):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {row['evaluation_mode']} | "
            f"{float(row['value']):.6f} | {float(row['delta_vs_global']):.6f} | {row['claim_status']} |"
        )

    lines.extend(
        [
            "",
            "## Subject-level Gain Snapshot",
            "",
            "| Variant | Track | Subject | Global | Personalized | Gain |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(per_subject_rows, key=lambda item: (item["track"], item["variant_name"], item["subject_id"]))[:24]:
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {row['subject_id']} | "
            f"{float(row['global_macro_f1']):.6f} | {float(row['personalized_macro_f1']):.6f} | "
            f"{float(row['gain_macro_f1']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Calibration Budget Sensitivity",
            "",
            "| Variant | Track | Budget (segments) | Global | Personalized | Gain |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(budget_rows, key=lambda item: (item["variant_name"], item["track"], int(item["calibration_segments"]))):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {int(row['calibration_segments'])} | "
            f"{float(row['global_macro_f1']):.6f} | {float(row['personalized_macro_f1']):.6f} | {float(row['gain']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Failure Analysis",
            "",
            "- Calibration mapping is label-efficient but may not improve classes unseen in the calibration subset.",
            "- Small per-subject test coverage can make gain estimates volatile.",
            "- This is a light personalization baseline; no model fine-tuning was performed.",
            "",
            "## Research Conclusion",
            "",
            "- `H2` establishes a reproducible light-personalization baseline with explicit global vs personalized comparison.",
            "- The next step (`H3`) should test stronger adaptation (subject-specific head/fine-tune) under the same leakage guards and reporting format.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_h3_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
) -> str:
    winners = report["comparison_summary"]["winner_by_track"]
    lines = [
        "# H3 Full Personalization Comparative Report",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Goal: {report['comparison_goal']}",
        f"- Full adaptation weight: `{report['calibration_policy']['full_adaptation_weight']}`",
        f"- Calibration segments per subject: `{report['calibration_policy']['calibration_segments_per_subject']}`",
        f"- Activity full-personalized winner: `{winners['activity']['variant_name']}` (`macro_f1={winners['activity']['value']}`, `delta_vs_global={winners['activity']['delta_vs_global']}`, `delta_vs_light={winners['activity']['delta_vs_light']}`).",
        f"- Arousal full-personalized winner: `{winners['arousal_coarse']['variant_name']}` (`macro_f1={winners['arousal_coarse']['value']}`, `delta_vs_global={winners['arousal_coarse']['delta_vs_global']}`, `delta_vs_light={winners['arousal_coarse']['delta_vs_light']}`).",
        "",
        "## Data Provenance",
        "",
        f"- Dataset: `{report['dataset_version']}`",
        f"- Label set: `{report['label_set_version']}`",
        f"- Preprocessing version: `{report['preprocessing_version']}`",
        f"- Split manifest: `{report['split_manifest_version']}`",
        f"- Exclusions: `{json.dumps(report['data_provenance']['exclusions'], ensure_ascii=False)}`",
        "",
        "## Results: Global vs Light vs Full",
        "",
        "| Variant | Track | Mode | macro_f1 | delta_vs_global | delta_vs_light | claim |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(comparison_rows, key=lambda item: (item["track"], item["variant_name"], item["evaluation_mode"])):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {row['evaluation_mode']} | "
            f"{float(row['value']):.6f} | {float(row['delta_vs_global']):.6f} | {float(row['delta_vs_light']):.6f} | {row['claim_status']} |"
        )

    lines.extend(
        [
            "",
            "## Subject-level Gains",
            "",
            "| Variant | Track | Subject | Global | Light | Full | Full-vs-Light |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(per_subject_rows, key=lambda item: (item["track"], item["variant_name"], item["subject_id"]))[:30]:
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {row['subject_id']} | "
            f"{float(row['global_macro_f1']):.6f} | {float(row['light_macro_f1']):.6f} | {float(row['full_macro_f1']):.6f} | "
            f"{float(row['gain_full_vs_light']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Calibration Budget Sensitivity",
            "",
            "| Variant | Track | Budget | Global | Light | Full | Full-vs-Global | Full-vs-Light |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(budget_rows, key=lambda item: (item["variant_name"], item["track"], int(item["calibration_segments"]))):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {int(row['calibration_segments'])} | "
            f"{float(row['global_macro_f1']):.6f} | {float(row['light_macro_f1']):.6f} | {float(row['full_macro_f1']):.6f} | "
            f"{float(row['gain_full_vs_global']):.6f} | {float(row['gain_full_vs_light']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Failure Analysis",
            "",
            "- Stronger adaptation can overfit when calibration subset is very small.",
            "- Performance stability remains constrained by low holdout subject count.",
            "- Full personalization should be interpreted jointly with worst-case degradation guardrail, not only average gain.",
            "",
            "## Research Conclusion",
            "",
            "- `H3` establishes full-personalization baseline under the same protocol as `H2`.",
            "- Next phase (`I1`) should aggregate `G/H` evidence into production-scope decision package.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_h5_report_markdown(
    report: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
) -> str:
    winners = report["comparison_summary"]["winner_by_track_label_free"]
    lines = [
        "# H5 Weak-label / Label-free Personalization Comparative Report",
        "",
        "## Experiment Summary",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Goal: {report['comparison_goal']}",
        f"- Adaptation weight: `{report['calibration_policy']['adaptation_weight']}`",
        f"- Calibration segments per subject: `{report['calibration_policy']['calibration_segments_per_subject']}`",
        f"- Activity label-free winner: `{winners['activity']['variant_name']}` (`macro_f1={winners['activity']['value']}`, `delta_vs_global={winners['activity']['delta_vs_global']}`, `delta_vs_weak_label={winners['activity']['delta_vs_weak_label']}`).",
        f"- Arousal label-free winner: `{winners['arousal_coarse']['variant_name']}` (`macro_f1={winners['arousal_coarse']['value']}`, `delta_vs_global={winners['arousal_coarse']['delta_vs_global']}`, `delta_vs_weak_label={winners['arousal_coarse']['delta_vs_weak_label']}`).",
        "",
        "## Data Provenance",
        "",
        f"- Dataset: `{report['dataset_version']}`",
        f"- Label set: `{report['label_set_version']}`",
        f"- Preprocessing version: `{report['preprocessing_version']}`",
        f"- Split manifest: `{report['split_manifest_version']}`",
        f"- Exclusions: `{json.dumps(report['data_provenance']['exclusions'], ensure_ascii=False)}`",
        "",
        "## Results: Global vs Weak-label vs Label-free",
        "",
        "| Variant | Track | Mode | macro_f1 | delta_vs_global | delta_vs_weak_label | claim |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(comparison_rows, key=lambda item: (item["track"], item["variant_name"], item["evaluation_mode"])):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {row['evaluation_mode']} | "
            f"{float(row['value']):.6f} | {float(row['delta_vs_global']):.6f} | {float(row['delta_vs_weak_label']):.6f} | {row['claim_status']} |"
        )

    lines.extend(
        [
            "",
            "## Subject-level Gains",
            "",
            "| Variant | Track | Subject | Global | Weak-label | Label-free | Label-free-vs-Global |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(per_subject_rows, key=lambda item: (item["track"], item["variant_name"], item["subject_id"]))[:30]:
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {row['subject_id']} | "
            f"{float(row['global_macro_f1']):.6f} | {float(row['weak_label_macro_f1']):.6f} | "
            f"{float(row['label_free_macro_f1']):.6f} | {float(row['gain_label_free_vs_global']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Calibration Budget Sensitivity",
            "",
            "| Variant | Track | Budget | Global | Weak-label | Label-free | Label-free-vs-Global |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(budget_rows, key=lambda item: (item["variant_name"], item["track"], int(item["calibration_segments"]))):
        lines.append(
            "| "
            f"{row['variant_name']} | {row['track']} | {int(row['calibration_segments'])} | "
            f"{float(row['global_macro_f1']):.6f} | {float(row['weak_label_macro_f1']):.6f} | "
            f"{float(row['label_free_macro_f1']):.6f} | {float(row['gain_label_free_vs_global']):.6f} |"
        )

    lines.extend(
        [
            "",
            "## Failure Analysis",
            "",
            "- Weak-label adaptation remains sensitive to calibration label noise.",
            "- Label-free pseudo-label adaptation can collapse to global behavior on hard subjects.",
            "- Results should be interpreted with per-subject degradation guardrails, not only mean gains.",
            "",
            "## Research Conclusion",
            "",
            "- `H5` provides reproducible comparison between weak-label and label-free personalization on the same split protocol.",
            "- Next step (`H6`) should define realtime/replay evaluation gates for deploying personalized policies safely.",
            "",
        ]
    )
    return "\n".join(lines)


def _generate_h2_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate H2 plots") from exc

    _plot_h2_gain_distribution(
        plt=plt,
        per_subject_rows=per_subject_rows,
        filename=plots_dir / "h2-gain-distribution.png",
    )
    _plot_h2_budget_sensitivity(
        plt=plt,
        comparison_rows=comparison_rows,
        budget_rows=budget_rows,
        filename=plots_dir / "h2-calibration-budget-sensitivity.png",
    )
    _plot_h2_worst_case_degradation(
        plt=plt,
        per_subject_rows=per_subject_rows,
        filename=plots_dir / "h2-worst-case-degradation.png",
    )


def _generate_h3_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate H3 plots") from exc

    _plot_h3_gain_distribution(
        plt=plt,
        per_subject_rows=per_subject_rows,
        filename=plots_dir / "h3-gain-distribution.png",
    )
    _plot_h3_budget_sensitivity(
        plt=plt,
        comparison_rows=comparison_rows,
        budget_rows=budget_rows,
        filename=plots_dir / "h3-calibration-budget-sensitivity.png",
    )
    _plot_h3_worst_case_degradation(
        plt=plt,
        per_subject_rows=per_subject_rows,
        filename=plots_dir / "h3-worst-case-degradation.png",
    )


def _generate_h5_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate H5 plots") from exc

    _plot_h5_gain_distribution(
        plt=plt,
        per_subject_rows=per_subject_rows,
        filename=plots_dir / "h5-gain-distribution.png",
    )
    _plot_h5_budget_sensitivity(
        plt=plt,
        comparison_rows=comparison_rows,
        budget_rows=budget_rows,
        filename=plots_dir / "h5-calibration-budget-sensitivity.png",
    )
    _plot_h5_worst_case_degradation(
        plt=plt,
        per_subject_rows=per_subject_rows,
        filename=plots_dir / "h5-worst-case-degradation.png",
    )


def _generate_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    variant_results: list[VariantRunResult],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate G2 plots") from exc

    activity_rows = [row for row in comparison_rows if row["track"] == "activity"]
    arousal_rows = [row for row in comparison_rows if row["track"] == "arousal_coarse"]
    _plot_metric_bars(
        plt=plt,
        rows=activity_rows,
        title="Activity Macro F1 by Variant",
        filename=plots_dir / "activity-macro-f1.png",
    )
    _plot_metric_bars(
        plt=plt,
        rows=arousal_rows,
        title="Arousal Macro F1 by Variant",
        filename=plots_dir / "arousal-macro-f1.png",
    )
    _plot_subject_breakdown(
        plt=plt,
        variant_results=variant_results,
        track="activity",
        filename=plots_dir / "subject-activity-macro-f1.png",
    )
    _plot_subject_breakdown(
        plt=plt,
        variant_results=variant_results,
        track="arousal_coarse",
        filename=plots_dir / "subject-arousal-macro-f1.png",
    )
    best_activity = max(variant_results, key=lambda item: item.tracks["activity"]["test"]["macro_f1"])
    best_arousal = max(variant_results, key=lambda item: item.tracks["arousal_coarse"]["test"]["macro_f1"])
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_activity.tracks["activity"]["test"],
        title=f"Activity Confusion Matrix ({best_activity.variant_name})",
        filename=plots_dir / "activity-confusion-matrix.png",
    )
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_arousal.tracks["arousal_coarse"]["test"],
        title=f"Arousal Confusion Matrix ({best_arousal.variant_name})",
        filename=plots_dir / "arousal-confusion-matrix.png",
    )


def _generate_model_zoo_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    feature_importance_rows: list[dict[str, Any]],
    variant_results: list[VariantRunResult],
    test_examples: list[SegmentExample],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate G3.1 plots") from exc

    activity_rows = [row for row in comparison_rows if row["track"] == "activity"]
    arousal_rows = [row for row in comparison_rows if row["track"] == "arousal_coarse"]
    _plot_ranked_metric_bars(
        plt=plt,
        rows=activity_rows,
        title="G3.1 Activity Macro F1 by Variant",
        filename=plots_dir / "g3-1-activity-macro-f1.png",
    )
    _plot_ranked_metric_bars(
        plt=plt,
        rows=arousal_rows,
        title="G3.1 Arousal Macro F1 by Variant",
        filename=plots_dir / "g3-1-arousal-macro-f1.png",
    )
    _plot_ranked_delta_bars(
        plt=plt,
        rows=activity_rows,
        title="G3.1 Activity Delta vs Watch-only Centroid",
        filename=plots_dir / "g3-1-activity-delta-vs-watch.png",
    )
    _plot_ranked_delta_bars(
        plt=plt,
        rows=arousal_rows,
        title="G3.1 Arousal Delta vs Watch-only Centroid",
        filename=plots_dir / "g3-1-arousal-delta-vs-watch.png",
    )
    _plot_top_subject_breakdown(
        plt=plt,
        comparison_rows=activity_rows,
        per_subject_rows=per_subject_rows,
        track="activity",
        filename=plots_dir / "g3-1-subject-activity-top-models.png",
    )
    _plot_top_subject_breakdown(
        plt=plt,
        comparison_rows=arousal_rows,
        per_subject_rows=per_subject_rows,
        track="arousal_coarse",
        filename=plots_dir / "g3-1-subject-arousal-top-models.png",
    )
    best_activity_name = max(activity_rows, key=lambda item: float(item["value"]))["variant_name"]
    best_arousal_name = max(arousal_rows, key=lambda item: float(item["value"]))["variant_name"]
    best_activity = next(item for item in variant_results if item.variant_name == best_activity_name)
    best_arousal = next(item for item in variant_results if item.variant_name == best_arousal_name)
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_activity.tracks["activity"]["test"],
        title=f"G3.1 Activity Confusion Matrix ({best_activity.variant_name})",
        filename=plots_dir / "g3-1-activity-confusion-matrix-best.png",
    )
    _plot_confusion_matrix(
        plt=plt,
        metrics=best_arousal.tracks["arousal_coarse"]["test"],
        title=f"G3.1 Arousal Confusion Matrix ({best_arousal.variant_name})",
        filename=plots_dir / "g3-1-arousal-confusion-matrix-best.png",
    )
    _plot_feature_importance_heatmap(
        plt=plt,
        feature_importance_rows=feature_importance_rows,
        winner_variant_names=[best_activity.variant_name, best_arousal.variant_name],
        filename=plots_dir / "g3-1-feature-importance-heatmap.png",
    )
    _plot_ordinal_scatter(
        plt=plt,
        y_true=[item.arousal_score for item in test_examples],
        y_pred=best_arousal.arousal_test_score_pred,
        title=f"G3.1 Ordinal Arousal Predictions ({best_arousal.variant_name})",
        filename=plots_dir / "g3-1-arousal-ordinal-scatter.png",
    )


def _generate_g3_1_loso_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    fold_metrics_rows: list[dict[str, Any]],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        return

    for track_name in ("activity", "arousal_coarse"):
        rows = [row for row in comparison_rows if row["track"] == track_name]
        if not rows:
            continue
        rows = sorted(rows, key=lambda item: float(item["mean_macro_f1"]), reverse=True)[:12]
        labels = [str(row["variant_name"]) for row in rows]
        means = [float(row["mean_macro_f1"]) for row in rows]
        lows = [float(row["ci95_low"]) for row in rows]
        highs = [float(row["ci95_high"]) for row in rows]
        yerr = np.asarray(
            [
                [max(0.0, mean - low) for mean, low in zip(means, lows)],
                [max(0.0, high - mean) for mean, high in zip(means, highs)],
            ],
            dtype=float,
        )

        fig, ax = plt.subplots(figsize=(14, 6))
        ax.bar(labels, means, yerr=yerr, color="#2B6CB0", alpha=0.9, capsize=4)
        ax.set_ylim(0.0, 1.0)
        ax.set_ylabel("macro_f1 (mean)")
        ax.set_title(f"G3.1 LOSO leaderboard ({track_name})")
        ax.tick_params(axis="x", rotation=35)
        fig.tight_layout()
        fig.savefig(plots_dir / f"g3-1-loso-leaderboard-{track_name}.png", dpi=160)
        plt.close(fig)

        top_variants = {str(row["variant_name"]) for row in rows[:8]}
        fold_rows = [
            row
            for row in fold_metrics_rows
            if row["track"] == track_name and row["variant_name"] in top_variants
        ]
        if not fold_rows:
            continue
        grouped: dict[str, list[float]] = {}
        for row in fold_rows:
            grouped.setdefault(str(row["variant_name"]), []).append(float(row["value"]))
        ordered = sorted(
            grouped.keys(),
            key=lambda name: float(np.mean(np.asarray(grouped[name], dtype=float))),
            reverse=True,
        )
        data = [grouped[name] for name in ordered]
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.boxplot(data, labels=ordered, patch_artist=True)
        ax.set_ylim(0.0, 1.0)
        ax.set_ylabel("macro_f1 by fold")
        ax.set_title(f"G3.1 LOSO fold distribution ({track_name})")
        ax.tick_params(axis="x", rotation=35)
        fig.tight_layout()
        fig.savefig(plots_dir / f"g3-1-loso-fold-distribution-{track_name}.png", dpi=160)
        plt.close(fig)


def _generate_g3_plots(
    plots_dir: Path,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError("matplotlib is required to generate G3 plots") from exc

    activity_rows = [row for row in comparison_rows if row["track"] == "activity"]
    arousal_rows = [row for row in comparison_rows if row["track"] == "arousal_coarse"]
    _plot_metric_bars(
        plt=plt,
        rows=activity_rows,
        title="G3 Activity Macro F1 (G1 + G2)",
        filename=plots_dir / "g3-activity-macro-f1.png",
    )
    _plot_metric_bars(
        plt=plt,
        rows=arousal_rows,
        title="G3 Arousal Macro F1 (G1 + G2)",
        filename=plots_dir / "g3-arousal-macro-f1.png",
    )
    _plot_delta_bars(
        plt=plt,
        rows=[row for row in activity_rows if row["source_step"] == "G2"],
        title="G3 Activity Delta vs Watch-only (G2 variants)",
        filename=plots_dir / "g3-activity-delta-vs-watch.png",
    )
    _plot_delta_bars(
        plt=plt,
        rows=[row for row in arousal_rows if row["source_step"] == "G2"],
        title="G3 Arousal Delta vs Watch-only (G2 variants)",
        filename=plots_dir / "g3-arousal-delta-vs-watch.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="activity",
        filename=plots_dir / "g3-subject-activity-macro-f1.png",
    )
    _plot_g3_subject_breakdown(
        plt=plt,
        rows=per_subject_rows,
        track="arousal_coarse",
        filename=plots_dir / "g3-subject-arousal-macro-f1.png",
    )


def _plot_metric_bars(plt: Any, rows: list[dict[str, Any]], title: str, filename: Path) -> None:
    variants = [row["variant_name"] for row in rows]
    values = [row["value"] for row in rows]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(variants, values, color=["#4C78A8", "#F58518", "#54A24B", "#E45756"][: len(rows)])
    ax.set_title(title)
    ax.set_ylabel("macro_f1")
    ax.set_ylim(0.0, 1.0)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_delta_bars(plt: Any, rows: list[dict[str, Any]], title: str, filename: Path) -> None:
    variants = [row["variant_name"] for row in rows]
    values = [float(row["delta_vs_watch_only"]) for row in rows]
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#4C78A8" if item >= 0 else "#E45756" for item in values]
    ax.bar(variants, values, color=colors)
    ax.axhline(y=0.0, color="black", linewidth=1.0, alpha=0.7)
    ax.set_title(title)
    ax.set_ylabel("delta_macro_f1")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_ranked_metric_bars(plt: Any, rows: list[dict[str, Any]], title: str, filename: Path) -> None:
    ordered = sorted(rows, key=lambda item: float(item["value"]), reverse=True)
    labels = [row["variant_name"] for row in ordered]
    values = [float(row["value"]) for row in ordered]
    colors = [_modality_color(str(row.get("modality_group", "custom"))) for row in ordered]
    fig_height = max(6.0, len(ordered) * 0.32)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    y_pos = np.arange(len(ordered))
    ax.barh(y_pos, values, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel("macro_f1")
    ax.set_xlim(0.0, 1.0)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_ranked_delta_bars(plt: Any, rows: list[dict[str, Any]], title: str, filename: Path) -> None:
    ordered = sorted(rows, key=lambda item: float(item["delta_vs_watch_only"]), reverse=True)
    labels = [row["variant_name"] for row in ordered]
    values = [float(row["delta_vs_watch_only"]) for row in ordered]
    colors = ["#2C7A7B" if item >= 0.0 else "#C05621" for item in values]
    fig_height = max(6.0, len(ordered) * 0.32)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    y_pos = np.arange(len(ordered))
    ax.barh(y_pos, values, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.axvline(x=0.0, color="black", linewidth=1.0, alpha=0.7)
    ax.set_title(title)
    ax.set_xlabel("delta_macro_f1")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_subject_breakdown(plt: Any, variant_results: list[VariantRunResult], track: str, filename: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = []
    series = []
    for result in variant_results:
        labels.append(result.variant_name)
        series.append(
            [
                row["macro_f1"]
                for row in result.per_subject_rows
                if row["track"] == track
            ]
        )
    ax.boxplot(series, labels=labels, patch_artist=True)
    ax.set_title(f"Per-subject macro_f1 distribution: {track}")
    ax.set_ylabel("macro_f1")
    ax.set_ylim(0.0, 1.0)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_top_subject_breakdown(
    plt: Any,
    comparison_rows: list[dict[str, Any]],
    per_subject_rows: list[dict[str, Any]],
    track: str,
    filename: Path,
    top_n: int = 8,
) -> None:
    top_variants = [
        row["variant_name"]
        for row in sorted(comparison_rows, key=lambda item: float(item["value"]), reverse=True)[:top_n]
    ]
    grouped: dict[str, list[float]] = {}
    for row in per_subject_rows:
        if row["track"] != track or row["variant_name"] not in top_variants:
            continue
        grouped.setdefault(str(row["variant_name"]), []).append(float(row["macro_f1"]))

    labels = [label for label in top_variants if label in grouped]
    series = [grouped[label] for label in labels]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.boxplot(series, labels=labels, patch_artist=True)
    ax.set_title(f"G3.1 per-subject macro_f1 distribution: {track}")
    ax.set_ylabel("macro_f1")
    ax.set_ylim(0.0, 1.0)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_g3_subject_breakdown(plt: Any, rows: list[dict[str, Any]], track: str, filename: Path) -> None:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        if row["track"] != track:
            continue
        grouped.setdefault(str(row["variant_name"]), []).append(float(row["macro_f1"]))
    labels = sorted(grouped.keys())
    series = [grouped[label] for label in labels]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot(series, labels=labels, patch_artist=True)
    ax.set_title(f"G3 per-subject macro_f1: {track}")
    ax.set_ylabel("macro_f1")
    ax.set_ylim(0.0, 1.0)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h2_gain_distribution(plt: Any, per_subject_rows: list[dict[str, Any]], filename: Path) -> None:
    grouped: dict[str, list[float]] = {}
    for row in per_subject_rows:
        key = f"{row['variant_name']}:{row['track']}"
        grouped.setdefault(key, []).append(float(row["gain_macro_f1"]))
    labels = sorted(grouped.keys())
    series = [grouped[label] for label in labels]
    fig_height = max(5.0, len(labels) * 0.45)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    ax.boxplot(series, labels=labels, patch_artist=True)
    ax.axhline(y=0.0, color="black", linewidth=1.0, linestyle="--", alpha=0.8)
    ax.set_title("H2 Subject-level Gain Distribution (Personalized - Global)")
    ax.set_ylabel("gain_macro_f1")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h2_budget_sensitivity(
    plt: Any,
    comparison_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
    filename: Path,
) -> None:
    best_variant_by_track: dict[str, str] = {}
    for track in ("activity", "arousal_coarse"):
        personalized_rows = [
            row for row in comparison_rows if row["track"] == track and row["evaluation_mode"] == "personalized"
        ]
        best_variant_by_track[track] = max(personalized_rows, key=lambda item: float(item["value"]))["variant_name"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for index, track in enumerate(("activity", "arousal_coarse")):
        ax = axes[index]
        variant_name = best_variant_by_track[track]
        rows = [
            row
            for row in budget_rows
            if row["track"] == track and row["variant_name"] == variant_name
        ]
        rows = sorted(rows, key=lambda item: int(item["calibration_segments"]))
        budgets = [int(row["calibration_segments"]) for row in rows]
        global_values = [float(row["global_macro_f1"]) for row in rows]
        personalized_values = [float(row["personalized_macro_f1"]) for row in rows]
        ax.plot(budgets, global_values, marker="o", color="#4A5568", label="global")
        ax.plot(budgets, personalized_values, marker="o", color="#2B6CB0", label="personalized")
        ax.set_title(f"{track} ({variant_name})")
        ax.set_xlabel("calibration_segments")
        if index == 0:
            ax.set_ylabel("macro_f1")
        ax.grid(alpha=0.25)
    axes[0].legend(loc="lower right")
    fig.suptitle("H2 Calibration Budget Sensitivity")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h2_worst_case_degradation(plt: Any, per_subject_rows: list[dict[str, Any]], filename: Path) -> None:
    grouped: dict[str, float] = {}
    for row in per_subject_rows:
        key = f"{row['variant_name']}:{row['track']}"
        gain = float(row["gain_macro_f1"])
        if key not in grouped or gain < grouped[key]:
            grouped[key] = gain
    labels = sorted(grouped.keys())
    values = [grouped[label] for label in labels]
    colors = ["#2F855A" if item >= 0.0 else "#C05621" for item in values]
    fig_height = max(4.0, len(labels) * 0.4)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color=colors)
    ax.axvline(x=0.0, color="black", linewidth=1.0, alpha=0.8)
    ax.axvline(x=-0.03, color="#D53F8C", linewidth=1.2, linestyle="--", alpha=0.9, label="guardrail=-0.03")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title("H2 Worst-case Subject-level Degradation")
    ax.set_xlabel("min_gain_macro_f1")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h3_gain_distribution(plt: Any, per_subject_rows: list[dict[str, Any]], filename: Path) -> None:
    grouped: dict[str, list[float]] = {}
    for row in per_subject_rows:
        key = f"{row['variant_name']}:{row['track']}:full_vs_light"
        grouped.setdefault(key, []).append(float(row["gain_full_vs_light"]))
    labels = sorted(grouped.keys())
    series = [grouped[label] for label in labels]
    fig_height = max(5.0, len(labels) * 0.45)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    ax.boxplot(series, labels=labels, patch_artist=True)
    ax.axhline(y=0.0, color="black", linewidth=1.0, linestyle="--", alpha=0.8)
    ax.set_title("H3 Subject-level Gain Distribution (Full - Light)")
    ax.set_ylabel("gain_macro_f1")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h3_budget_sensitivity(
    plt: Any,
    comparison_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
    filename: Path,
) -> None:
    best_variant_by_track: dict[str, str] = {}
    for track in ("activity", "arousal_coarse"):
        full_rows = [row for row in comparison_rows if row["track"] == track and row["evaluation_mode"] == "full"]
        best_variant_by_track[track] = max(full_rows, key=lambda item: float(item["value"]))["variant_name"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for index, track in enumerate(("activity", "arousal_coarse")):
        ax = axes[index]
        variant_name = best_variant_by_track[track]
        rows = [
            row
            for row in budget_rows
            if row["track"] == track and row["variant_name"] == variant_name
        ]
        rows = sorted(rows, key=lambda item: int(item["calibration_segments"]))
        budgets = [int(row["calibration_segments"]) for row in rows]
        light_values = [float(row["light_macro_f1"]) for row in rows]
        full_values = [float(row["full_macro_f1"]) for row in rows]
        ax.plot(budgets, light_values, marker="o", color="#2B6CB0", label="light")
        ax.plot(budgets, full_values, marker="o", color="#C53030", label="full")
        ax.set_title(f"{track} ({variant_name})")
        ax.set_xlabel("calibration_segments")
        if index == 0:
            ax.set_ylabel("macro_f1")
        ax.grid(alpha=0.25)
    axes[0].legend(loc="lower right")
    fig.suptitle("H3 Calibration Budget Sensitivity")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h3_worst_case_degradation(plt: Any, per_subject_rows: list[dict[str, Any]], filename: Path) -> None:
    grouped: dict[str, float] = {}
    for row in per_subject_rows:
        key = f"{row['variant_name']}:{row['track']}"
        gain = float(row["gain_full_vs_global"])
        if key not in grouped or gain < grouped[key]:
            grouped[key] = gain
    labels = sorted(grouped.keys())
    values = [grouped[label] for label in labels]
    colors = ["#2F855A" if item >= 0.0 else "#C05621" for item in values]
    fig_height = max(4.0, len(labels) * 0.4)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color=colors)
    ax.axvline(x=0.0, color="black", linewidth=1.0, alpha=0.8)
    ax.axvline(x=-0.03, color="#D53F8C", linewidth=1.2, linestyle="--", alpha=0.9, label="guardrail=-0.03")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title("H3 Worst-case Subject-level Degradation (Full vs Global)")
    ax.set_xlabel("min_gain_macro_f1")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h5_gain_distribution(plt: Any, per_subject_rows: list[dict[str, Any]], filename: Path) -> None:
    grouped: dict[str, list[float]] = {}
    for row in per_subject_rows:
        key = f"{row['variant_name']}:{row['track']}:label_free_vs_global"
        grouped.setdefault(key, []).append(float(row["gain_label_free_vs_global"]))
    labels = sorted(grouped.keys())
    series = [grouped[label] for label in labels]
    fig_height = max(5.0, len(labels) * 0.45)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    ax.boxplot(series, labels=labels, patch_artist=True)
    ax.axhline(y=0.0, color="black", linewidth=1.0, linestyle="--", alpha=0.8)
    ax.set_title("H5 Subject-level Gain Distribution (Label-free - Global)")
    ax.set_ylabel("gain_macro_f1")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h5_budget_sensitivity(
    plt: Any,
    comparison_rows: list[dict[str, Any]],
    budget_rows: list[dict[str, Any]],
    filename: Path,
) -> None:
    best_variant_by_track: dict[str, str] = {}
    for track in ("activity", "arousal_coarse"):
        label_free_rows = [
            row for row in comparison_rows if row["track"] == track and row["evaluation_mode"] == "label_free"
        ]
        best_variant_by_track[track] = max(label_free_rows, key=lambda item: float(item["value"]))["variant_name"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for index, track in enumerate(("activity", "arousal_coarse")):
        ax = axes[index]
        variant_name = best_variant_by_track[track]
        rows = [
            row
            for row in budget_rows
            if row["track"] == track and row["variant_name"] == variant_name
        ]
        rows = sorted(rows, key=lambda item: int(item["calibration_segments"]))
        budgets = [int(row["calibration_segments"]) for row in rows]
        global_values = [float(row["global_macro_f1"]) for row in rows]
        weak_values = [float(row["weak_label_macro_f1"]) for row in rows]
        label_free_values = [float(row["label_free_macro_f1"]) for row in rows]
        ax.plot(budgets, global_values, marker="o", color="#4A5568", label="global")
        ax.plot(budgets, weak_values, marker="o", color="#2B6CB0", label="weak_label")
        ax.plot(budgets, label_free_values, marker="o", color="#C53030", label="label_free")
        ax.set_title(f"{track} ({variant_name})")
        ax.set_xlabel("calibration_segments")
        if index == 0:
            ax.set_ylabel("macro_f1")
        ax.grid(alpha=0.25)
    axes[0].legend(loc="lower right")
    fig.suptitle("H5 Calibration Budget Sensitivity")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_h5_worst_case_degradation(plt: Any, per_subject_rows: list[dict[str, Any]], filename: Path) -> None:
    grouped: dict[str, float] = {}
    for row in per_subject_rows:
        key = f"{row['variant_name']}:{row['track']}"
        gain = float(row["gain_label_free_vs_global"])
        if key not in grouped or gain < grouped[key]:
            grouped[key] = gain
    labels = sorted(grouped.keys())
    values = [grouped[label] for label in labels]
    colors = ["#2F855A" if item >= 0.0 else "#C05621" for item in values]
    fig_height = max(4.0, len(labels) * 0.4)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color=colors)
    ax.axvline(x=0.0, color="black", linewidth=1.0, alpha=0.8)
    ax.axvline(x=-0.05, color="#D53F8C", linewidth=1.2, linestyle="--", alpha=0.9, label="guardrail=-0.05")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title("H5 Worst-case Subject-level Degradation (Label-free vs Global)")
    ax.set_xlabel("min_gain_macro_f1")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_feature_importance_heatmap(
    plt: Any,
    feature_importance_rows: list[dict[str, Any]],
    winner_variant_names: list[str],
    filename: Path,
) -> None:
    filtered = [
        row
        for row in feature_importance_rows
        if row["variant_name"] in set(winner_variant_names) and int(row["rank"]) <= 12
    ]
    if not filtered:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No feature importance available", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(filename, dpi=160)
        plt.close(fig)
        return

    feature_names = []
    for row in filtered:
        if row["feature_name"] not in feature_names:
            feature_names.append(str(row["feature_name"]))
    columns = []
    for variant_name in winner_variant_names:
        for track_name in ("activity", "arousal_coarse"):
            if any(
                row["variant_name"] == variant_name and row["track"] == track_name
                for row in filtered
            ):
                columns.append((variant_name, track_name))

    matrix = np.zeros((len(feature_names), len(columns)), dtype=float)
    for col_idx, (variant_name, track_name) in enumerate(columns):
        for row in filtered:
            if row["variant_name"] == variant_name and row["track"] == track_name:
                row_idx = feature_names.index(str(row["feature_name"]))
                matrix[row_idx, col_idx] = float(row["importance_abs"])

    fig_width = max(8.0, len(columns) * 2.2)
    fig_height = max(6.0, len(feature_names) * 0.35)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    image = ax.imshow(matrix, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels([f"{variant}\n{track}" for variant, track in columns], rotation=30, ha="right")
    ax.set_yticks(range(len(feature_names)))
    ax.set_yticklabels(feature_names)
    ax.set_title("G3.1 Top Feature Importance Heatmap")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_confusion_matrix(plt: Any, metrics: dict[str, Any], title: str, filename: Path) -> None:
    cm = np.asarray(metrics["confusion_matrix"], dtype=float)
    labels = metrics["labels"]
    fig, ax = plt.subplots(figsize=(6, 5))
    image = ax.imshow(cm, cmap="Blues")
    ax.set_title(title)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for row_idx in range(cm.shape[0]):
        for col_idx in range(cm.shape[1]):
            ax.text(col_idx, row_idx, int(cm[row_idx, col_idx]), ha="center", va="center", color="black")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _plot_ordinal_scatter(plt: Any, y_true: list[int], y_pred: list[int], title: str, filename: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(y_true, y_pred, color="#2B6CB0", alpha=0.8)
    ax.plot([1, 9], [1, 9], color="#718096", linewidth=1.2, linestyle="--")
    ax.set_title(title)
    ax.set_xlabel("true_arousal_score")
    ax.set_ylabel("predicted_arousal_score")
    ax.set_xlim(1, 9)
    ax.set_ylim(1, 9)
    fig.tight_layout()
    fig.savefig(filename, dpi=160)
    plt.close(fig)


def _modality_color(modality_group: str) -> str:
    palette = {
        "watch_only": "#2B6CB0",
        "chest_only": "#B7791F",
        "fusion": "#2F855A",
        "polar_only": "#805AD5",
        "watch_motion_only": "#2B6CB0",
        "polar_plus_watch_motion": "#319795",
        "custom": "#4A5568",
    }
    return palette.get(modality_group, "#4A5568")


def _coarse_class_score_mapping(arousal_scores: list[int], arousal_classes: list[str]) -> dict[str, int]:
    grouped: dict[str, list[int]] = {}
    for score, coarse in zip(arousal_scores, arousal_classes):
        grouped.setdefault(coarse, []).append(score)
    return {label: int(round(float(np.median(values)))) for label, values in grouped.items()}


def _bootstrap_pairwise_delta_ci(
    examples: list[SegmentExample],
    predicted_a: list[str],
    predicted_b: list[str],
    target_field: str,
    seed: int = 42,
    iterations: int = 800,
) -> list[float | None]:
    grouped: dict[str, list[int]] = {}
    for idx, example in enumerate(examples):
        grouped.setdefault(example.subject_id, []).append(idx)
    subjects = sorted(grouped.keys())
    if len(subjects) < 2:
        return [None, None]

    rng = np.random.default_rng(seed)
    delta_samples = []
    for _ in range(iterations):
        sampled_subjects = rng.choice(subjects, size=len(subjects), replace=True)
        indices: list[int] = []
        for subject in sampled_subjects:
            indices.extend(grouped[str(subject)])
        truth = [str(getattr(examples[i], target_field)) for i in indices]
        pred_a = [predicted_a[i] for i in indices]
        pred_b = [predicted_b[i] for i in indices]
        metric_a = compute_classification_metrics(truth, pred_a).macro_f1
        metric_b = compute_classification_metrics(truth, pred_b).macro_f1
        delta_samples.append(metric_a - metric_b)

    return [
        round(float(np.percentile(delta_samples, 2.5)), 6),
        round(float(np.percentile(delta_samples, 97.5)), 6),
    ]


def _claim_status_from_delta(delta_value: float, delta_ci: list[float | None]) -> str:
    low, high = delta_ci
    if low is None or high is None:
        return "insufficient_subjects"
    if low > 0.0:
        return "supported"
    if high < 0.0:
        return "regression"
    if delta_value > 0.0:
        return "inconclusive_positive"
    if delta_value < 0.0:
        return "inconclusive_negative"
    return "inconclusive"


def _majority_label(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    sorted_items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return sorted_items[0][0]


def _arousal_coarse_class(score: int) -> str:
    if score <= 3:
        return "low"
    if score <= 6:
        return "medium"
    return "high"


def _valence_coarse_class(score: int) -> str:
    if score <= 3:
        return "negative"
    if score <= 6:
        return "neutral"
    return "positive"


def _subject_code_from_session_id(session_id: str) -> str | None:
    tokens = session_id.split(":")
    if len(tokens) < 3:
        return None
    subject_token = tokens[2]
    if not subject_token.startswith("S"):
        return None
    return subject_token


def _split_subject_index(split_manifest: dict[str, Any]) -> dict[str, str]:
    index: dict[str, str] = {}
    for subject_id in split_manifest.get("train_subject_ids", []):
        index[str(subject_id)] = "train"
    for subject_id in split_manifest.get("validation_subject_ids", []):
        index[str(subject_id)] = "validation"
    for subject_id in split_manifest.get("test_subject_ids", []):
        index[str(subject_id)] = "test"
    return index


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows
