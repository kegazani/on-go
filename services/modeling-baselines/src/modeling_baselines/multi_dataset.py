from __future__ import annotations

import csv
import io
import json
import pickle
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from modeling_baselines.estimators import build_estimator_classifier, get_classifier_config
from modeling_baselines.metrics import compute_classification_metrics
from modeling_baselines.pipeline import (
    CentroidClassifier,
    GaussianNBClassifier,
    _extract_multimodal_features,
    _load_wesad_streams,
)

UNSAFE_FEATURE_PREFIXES = ("label_", "meta_")
PRIMARY_AROUSAL_DATASETS = {"grex"}
PROTOCOL_MAPPED_AROUSAL_DATASETS = {"wesad"}


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    dataset_version: str


@dataclass(frozen=True)
class Example:
    dataset_id: str
    dataset_version: str
    subject_id: str
    session_id: str
    segment_id: str
    split: str
    activity_label: str
    arousal_coarse: str
    features: dict[str, float]


@dataclass
class _SignalFeatureContext:
    artifacts_root: Path
    wesad_streams_cache: dict[str, dict[str, np.ndarray]]
    grex_payload: dict[str, list[Any]] | None
    emowear_feature_cache: dict[str, dict[str, float]]


def run_multi_dataset_benchmark(
    artifacts_root: Path,
    min_confidence: float = 0.5,
) -> dict[str, Any]:
    dataset_specs = [
        DatasetSpec(dataset_id="wesad", dataset_version="wesad-v1"),
        DatasetSpec(dataset_id="grex", dataset_version="grex-v1"),
        DatasetSpec(dataset_id="emowear", dataset_version="emowear-v1"),
        DatasetSpec(dataset_id="dapper", dataset_version="dapper-v1"),
    ]

    variants = [
        ("label_centroid", "centroid", "nearest_centroid_label_features"),
        ("label_gaussian_nb", "gaussian_nb", "gaussian_nb_label_features"),
        ("label_logistic_regression", "logistic_regression", get_classifier_config("logistic_regression").model_family),
        ("label_random_forest", "random_forest", get_classifier_config("random_forest").model_family),
        ("label_xgboost", "xgboost", get_classifier_config("xgboost").model_family),
        ("label_lightgbm", "lightgbm", get_classifier_config("lightgbm").model_family),
        ("label_catboost", "catboost", get_classifier_config("catboost").model_family),
    ]

    output_root = artifacts_root / "multi-dataset" / "comparison"
    plots_dir = output_root / "plots"
    output_root.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    model_rows: list[dict[str, Any]] = []
    predictions_rows: list[dict[str, Any]] = []
    per_subject_rows: list[dict[str, Any]] = []
    dataset_summaries: list[dict[str, Any]] = []
    skipped_datasets: list[dict[str, Any]] = []
    failed_variants: list[dict[str, Any]] = []
    feature_context = _new_signal_feature_context(artifacts_root)

    for spec in dataset_specs:
        dataset_root = _resolve_dataset_root(artifacts_root, spec.dataset_id, spec.dataset_version)
        labels_path = dataset_root / "unified" / "segment-labels.jsonl"
        split_path = dataset_root / "manifest" / "split-manifest.json"
        if not labels_path.exists() or not split_path.exists():
            skipped_datasets.append(
                {
                    "dataset_id": spec.dataset_id,
                    "dataset_version": spec.dataset_version,
                    "reason": "missing unified labels or split manifest",
                }
            )
            continue

        labels = _load_jsonl(labels_path)
        split_manifest = _load_json(split_path)
        examples = _build_examples(
            labels=labels,
            split_manifest=split_manifest,
            dataset_id=spec.dataset_id,
            dataset_version=spec.dataset_version,
            min_confidence=min_confidence,
            feature_context=feature_context,
        )

        train = [item for item in examples if item.split == "train"]
        test = [item for item in examples if item.split == "test"]
        if not train or not test:
            skipped_datasets.append(
                {
                    "dataset_id": spec.dataset_id,
                    "dataset_version": spec.dataset_version,
                    "reason": "insufficient train/test examples after filtering",
                }
            )
            continue

        feature_names = _select_safe_feature_names(sorted(examples[0].features.keys()))
        if not feature_names:
            skipped_datasets.append(
                {
                    "dataset_id": spec.dataset_id,
                    "dataset_version": spec.dataset_version,
                    "reason": "no safe non-label features available; harmonized signal features are required",
                }
            )
            continue
        x_train = _to_matrix(train, feature_names)
        x_test = _to_matrix(test, feature_names)
        activity_train = [item.activity_label for item in train]
        activity_test = [item.activity_label for item in test]
        arousal_train = [item.arousal_coarse for item in train]
        arousal_test = [item.arousal_coarse for item in test]
        activity_track_enabled = len(set(activity_train)) > 1 and len(set(activity_test)) > 1
        arousal_track_enabled = len(set(arousal_train)) > 1 and len(set(arousal_test)) > 1

        dataset_track_rows: list[dict[str, Any]] = []
        for variant_name, classifier_kind, model_family in variants:
            arousal_pred = None
            activity_pred = [None] * len(test)
            if activity_track_enabled:
                try:
                    activity_pred = _fit_predict(classifier_kind, x_train, activity_train, x_test)
                    activity_metrics = compute_classification_metrics(activity_test, activity_pred)
                    model_rows.append(
                        {
                            "dataset_id": spec.dataset_id,
                            "dataset_version": spec.dataset_version,
                            "variant_name": variant_name,
                            "classifier_kind": classifier_kind,
                            "model_family": model_family,
                            "track": "activity",
                            "metric_name": "macro_f1",
                            "split": "test",
                            "value": activity_metrics.macro_f1,
                        }
                    )
                    dataset_track_rows.append(
                        {
                            "dataset_id": spec.dataset_id,
                            "track": "activity",
                            "variant_name": variant_name,
                            "value": activity_metrics.macro_f1,
                        }
                    )
                except Exception as exc:
                    failed_variants.append(
                        {
                            "dataset_id": spec.dataset_id,
                            "dataset_version": spec.dataset_version,
                            "variant_name": variant_name,
                            "track": "activity",
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        }
                    )

            if arousal_track_enabled:
                try:
                    arousal_pred = _fit_predict(classifier_kind, x_train, arousal_train, x_test)
                    arousal_metrics = compute_classification_metrics(arousal_test, arousal_pred)
                    model_rows.append(
                        {
                            "dataset_id": spec.dataset_id,
                            "dataset_version": spec.dataset_version,
                            "variant_name": variant_name,
                            "classifier_kind": classifier_kind,
                            "model_family": model_family,
                            "track": "arousal_coarse",
                            "metric_name": "macro_f1",
                            "split": "test",
                            "value": arousal_metrics.macro_f1,
                        }
                    )
                    dataset_track_rows.append(
                        {
                            "dataset_id": spec.dataset_id,
                            "track": "arousal_coarse",
                            "variant_name": variant_name,
                            "value": arousal_metrics.macro_f1,
                        }
                    )
                except Exception as exc:
                    failed_variants.append(
                        {
                            "dataset_id": spec.dataset_id,
                            "dataset_version": spec.dataset_version,
                            "variant_name": variant_name,
                            "track": "arousal_coarse",
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        }
                    )

            for example, activity_item, arousal_item in zip(
                test,
                activity_pred,
                arousal_pred if arousal_pred is not None else [None] * len(test),
            ):
                predictions_rows.append(
                    {
                        "dataset_id": spec.dataset_id,
                        "dataset_version": spec.dataset_version,
                        "variant_name": variant_name,
                        "subject_id": example.subject_id,
                        "session_id": example.session_id,
                        "segment_id": example.segment_id,
                        "activity_true": example.activity_label,
                        "activity_pred": activity_item,
                        "arousal_coarse_true": example.arousal_coarse,
                        "arousal_coarse_pred": arousal_item,
                    }
                )

            per_subject_rows.extend(
                _subject_rows(
                    dataset_id=spec.dataset_id,
                    variant_name=variant_name,
                    test_examples=test,
                    activity_pred=activity_pred if activity_track_enabled else None,
                    arousal_pred=arousal_pred if arousal_track_enabled else None,
                )
            )

        summary = {
            "dataset_id": spec.dataset_id,
            "dataset_version": spec.dataset_version,
            "subjects": len({item.subject_id for item in examples}),
            "segments": len(examples),
            "winner_activity": _winner(dataset_track_rows, "activity"),
            "winner_arousal": _winner(dataset_track_rows, "arousal_coarse"),
        }
        dataset_summaries.append(summary)

    experiment_id = f"g3-2-multi-dataset-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report = {
        "experiment_id": experiment_id,
        "comparison_scope": "multi-dataset benchmark on unified segment labels and provenance features",
        "datasets_considered": [item.__dict__ for item in dataset_specs],
        "datasets_benchmarked": dataset_summaries,
        "skipped_datasets": skipped_datasets,
        "failed_variants": failed_variants,
        "model_comparison": model_rows,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    (output_root / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_root / "model-comparison.csv", model_rows)
    _write_csv(output_root / "predictions-test.csv", predictions_rows)
    _write_csv(output_root / "per-subject-metrics.csv", per_subject_rows)
    _write_csv(output_root / "failed-variants.csv", failed_variants)
    (output_root / "research-report.md").write_text(_build_report_md(report), encoding="utf-8")
    _generate_plots(plots_dir=plots_dir, rows=model_rows)

    return {
        "experiment_id": experiment_id,
        "report_path": str(output_root / "evaluation-report.json"),
        "model_comparison_path": str(output_root / "model-comparison.csv"),
        "predictions_path": str(output_root / "predictions-test.csv"),
        "per_subject_path": str(output_root / "per-subject-metrics.csv"),
        "failed_variants_path": str(output_root / "failed-variants.csv"),
        "research_report_path": str(output_root / "research-report.md"),
        "plots_dir": str(plots_dir),
        "dataset_count": len(dataset_summaries),
        "skipped_dataset_count": len(skipped_datasets),
    }


def run_multi_dataset_training_strategy(
    artifacts_root: Path,
    registry_path: Path,
    min_confidence: float = 0.5,
) -> dict[str, Any]:
    output_root = artifacts_root / "multi-dataset" / "strategy"
    output_root.mkdir(parents=True, exist_ok=True)

    dataset_rows = _build_dataset_strategy_rows(
        artifacts_root=artifacts_root,
        registry_path=registry_path,
        min_confidence=min_confidence,
    )
    training_phases = _build_training_phases(dataset_rows)
    experiment_id = f"g3-2-multi-dataset-strategy-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report = {
        "experiment_id": experiment_id,
        "strategy_scope": "Recommend a claim-safe multi-dataset arousal training protocol using real, protocol-mapped, and proxy label tiers.",
        "registry_path": str(registry_path),
        "datasets_considered": [
            {
                "dataset_id": row["dataset_id"],
                "dataset_version": row["dataset_version"],
                "label_quality_tier": row["label_quality_tier"],
                "recommended_role": row["recommended_role"],
                "coverage_status": row["coverage_status"],
            }
            for row in dataset_rows
        ],
        "dataset_strategy": dataset_rows,
        "recommended_training_phases": training_phases,
        "synthetic_data_policy": {
            "allowed": "augmentation_only",
            "disallowed": [
                "synthetic data as primary supervised arousal source",
                "synthetic-only model selection claims",
            ],
            "notes": [
                "Use synthetic data only for robustness augmentation or self-supervised pretraining.",
                "Final model selection must rely on real-label datasets only.",
            ],
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    report_path = output_root / "training-strategy-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dataset_strategy_path = output_root / "dataset-strategy.csv"
    _write_csv(dataset_strategy_path, dataset_rows)

    training_phases_path = output_root / "training-phases.csv"
    _write_csv(training_phases_path, training_phases)

    protocol_md_path = output_root / "training-protocol.md"
    protocol_md_path.write_text(_build_training_protocol_md(report), encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "dataset_strategy_path": str(dataset_strategy_path),
        "training_phases_path": str(training_phases_path),
        "training_protocol_path": str(protocol_md_path),
        "dataset_count": len(dataset_rows),
    }


def run_multi_dataset_training_protocol(
    artifacts_root: Path,
    registry_path: Path,
    min_confidence: float = 0.5,
) -> dict[str, Any]:
    output_root = artifacts_root / "multi-dataset" / "protocol-execution"
    output_root.mkdir(parents=True, exist_ok=True)

    dataset_rows = _build_dataset_strategy_rows(
        artifacts_root=artifacts_root,
        registry_path=registry_path,
        min_confidence=min_confidence,
    )
    training_phases = _build_training_phases(dataset_rows)
    readiness_rows = _build_protocol_readiness_rows(dataset_rows)
    phase_rows = _build_phase_execution_rows(training_phases, readiness_rows)

    failed_checks = [row for row in readiness_rows if row["status"] == "failed"]
    blocked_phases = [row for row in phase_rows if row["status"] == "blocked"]
    overall_status = "ready" if not failed_checks and not blocked_phases else "blocked"

    experiment_id = f"g3-2-multi-dataset-protocol-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report = {
        "experiment_id": experiment_id,
        "execution_scope": "Execute and gate the multi-dataset arousal training protocol with readiness checks.",
        "registry_path": str(registry_path),
        "overall_status": overall_status,
        "dataset_strategy": dataset_rows,
        "training_phases": training_phases,
        "readiness_checks": readiness_rows,
        "phase_execution": phase_rows,
        "blocking_checks": failed_checks,
        "blocking_phases": blocked_phases,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    report_path = output_root / "protocol-execution-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readiness_path = output_root / "readiness-checks.csv"
    _write_csv(readiness_path, readiness_rows)
    phase_path = output_root / "phase-execution.csv"
    _write_csv(phase_path, phase_rows)
    protocol_md_path = output_root / "protocol-execution.md"
    protocol_md_path.write_text(_build_protocol_execution_md(report), encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "readiness_checks_path": str(readiness_path),
        "phase_execution_path": str(phase_path),
        "protocol_execution_path": str(protocol_md_path),
        "overall_status": overall_status,
        "blocking_check_count": len(failed_checks),
        "blocking_phase_count": len(blocked_phases),
    }


def run_multi_dataset_self_training_scaffold(
    artifacts_root: Path,
    registry_path: Path,
    min_confidence: float = 0.5,
) -> dict[str, Any]:
    output_root = artifacts_root / "multi-dataset" / "self-training-scaffold"
    output_root.mkdir(parents=True, exist_ok=True)

    dataset_rows = _build_dataset_strategy_rows(
        artifacts_root=artifacts_root,
        registry_path=registry_path,
        min_confidence=min_confidence,
    )
    training_phases = _build_training_phases(dataset_rows)
    readiness_rows = _build_protocol_readiness_rows(dataset_rows)
    protocol_phase_rows = _build_phase_execution_rows(training_phases, readiness_rows)
    self_training_phases = _build_self_training_phase_rows(
        protocol_phase_rows=protocol_phase_rows,
        readiness_rows=readiness_rows,
    )
    metrics_contract = _build_self_training_metrics_contract()

    blocking_checks = [row for row in readiness_rows if row["status"] == "failed"]
    blocked_self_training_phases = [row for row in self_training_phases if row["status"] == "blocked"]
    overall_status = "ready" if not blocking_checks and not blocked_self_training_phases else "blocked"

    experiment_id = f"g3-2-self-training-scaffold-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report = {
        "experiment_id": experiment_id,
        "execution_scope": "Build a runnable multi-dataset self-training scaffold from strategy/protocol readiness.",
        "registry_path": str(registry_path),
        "overall_status": overall_status,
        "dataset_strategy": dataset_rows,
        "protocol_phase_execution": protocol_phase_rows,
        "self_training_phases": self_training_phases,
        "metrics_contract": metrics_contract,
        "blocking_checks": blocking_checks,
        "blocking_self_training_phases": blocked_self_training_phases,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    report_path = output_root / "self-training-scaffold-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    phase_plan_path = output_root / "self-training-phases.csv"
    _write_csv(phase_plan_path, self_training_phases)
    metrics_path = output_root / "metrics-contract.csv"
    _write_csv(metrics_path, metrics_contract)
    runbook_path = output_root / "self-training-runbook.md"
    runbook_path.write_text(_build_self_training_runbook_md(report), encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "phase_plan_path": str(phase_plan_path),
        "metrics_contract_path": str(metrics_path),
        "runbook_path": str(runbook_path),
        "overall_status": overall_status,
        "blocking_check_count": len(blocking_checks),
        "blocking_phase_count": len(blocked_self_training_phases),
    }


def run_multi_dataset_self_training_execution(
    artifacts_root: Path,
    registry_path: Path,
    min_confidence: float = 0.5,
) -> dict[str, Any]:
    output_root = artifacts_root / "multi-dataset" / "self-training-execution"
    output_root.mkdir(parents=True, exist_ok=True)

    dataset_rows = _build_dataset_strategy_rows(
        artifacts_root=artifacts_root,
        registry_path=registry_path,
        min_confidence=min_confidence,
    )
    training_phases = _build_training_phases(dataset_rows)
    readiness_rows = _build_protocol_readiness_rows(dataset_rows)
    protocol_phase_rows = _build_phase_execution_rows(training_phases, readiness_rows)
    self_training_phases = _build_self_training_phase_rows(protocol_phase_rows, readiness_rows)

    phase0 = {
        "phase_name": "freeze_gates",
        "status": "ready" if not any(row["status"] == "failed" for row in readiness_rows) else "blocked",
        "readiness_checks": readiness_rows,
        "protocol_phase_execution": protocol_phase_rows,
    }
    (output_root / "phase-0-freeze-gates.json").write_text(
        json.dumps(phase0, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if phase0["status"] != "ready":
        experiment_id = f"g3-2-self-training-execution-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        blocked_report = {
            "experiment_id": experiment_id,
            "overall_status": "blocked",
            "dataset_strategy": dataset_rows,
            "readiness_checks": readiness_rows,
            "protocol_phase_execution": protocol_phase_rows,
            "self_training_phases": self_training_phases,
            "blocking_reason": "failed readiness checks",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        report_path = output_root / "self-training-execution-report.json"
        report_path.write_text(json.dumps(blocked_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {
            "experiment_id": experiment_id,
            "report_path": str(report_path),
            "overall_status": "blocked",
            "blocking_check_count": len([row for row in readiness_rows if row["status"] == "failed"]),
            "blocking_phase_count": len([row for row in self_training_phases if row["status"] == "blocked"]),
        }

    examples_by_dataset = _load_ready_dataset_examples_by_split(
        artifacts_root=artifacts_root,
        dataset_rows=dataset_rows,
        min_confidence=min_confidence,
    )
    candidate_kinds = ["gaussian_nb", "logistic_regression", "xgboost", "catboost"]
    phase_reports: dict[str, Any] = {"phase_0": phase0}

    proxy_key = _first_dataset_key_by_role(dataset_rows, "auxiliary_pretraining")
    real_key = _first_dataset_key_by_role(dataset_rows, "primary_supervision")
    protocol_key = _first_dataset_key_by_role(dataset_rows, "protocol_transfer_or_eval")
    if proxy_key is None or real_key is None or protocol_key is None:
        raise ValueError("missing required dataset role for self-training execution")

    phase1 = _run_phase_train_eval(
        phase_name="proxy_pretraining",
        dataset_key=proxy_key,
        candidate_kinds=candidate_kinds,
        examples_by_dataset=examples_by_dataset,
    )
    phase_reports["phase_1"] = phase1
    (output_root / "phase-1-proxy-pretraining.json").write_text(json.dumps(phase1, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    phase2 = _run_phase_train_eval(
        phase_name="real_label_finetune",
        dataset_key=real_key,
        candidate_kinds=candidate_kinds,
        examples_by_dataset=examples_by_dataset,
    )
    phase_reports["phase_2"] = phase2
    (output_root / "phase-2-real-label-finetune.json").write_text(json.dumps(phase2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    teacher_kind = str(phase2.get("winner_arousal_kind", "gaussian_nb"))
    runner_up_kind = str(phase2.get("runner_up_arousal_kind", teacher_kind))
    committee_kinds = list(dict.fromkeys(phase2.get("top_arousal_kinds", [teacher_kind, runner_up_kind])[:3]))
    if not committee_kinds:
        committee_kinds = [teacher_kind]

    real_bundle = examples_by_dataset[real_key]
    real_feature_names = _select_safe_feature_names(sorted(real_bundle["feature_names"]))
    real_train = real_bundle["train"]
    real_test = real_bundle["test"]
    x_real_train = _to_matrix(real_train, real_feature_names)
    y_real_arousal = [item.arousal_coarse for item in real_train]

    committee_models: dict[str, Any] = {}
    for kind in committee_kinds:
        committee_models[kind] = _fit_model(kind, x_real_train, y_real_arousal)
    teacher_model = committee_models[teacher_kind]

    phase3 = _run_phase_transfer_eval(
        phase_name="protocol_transfer",
        dataset_key=protocol_key,
        model_kind=teacher_kind,
        model=teacher_model,
        feature_names=real_feature_names,
        examples_by_dataset=examples_by_dataset,
    )
    phase_reports["phase_3"] = phase3
    (output_root / "phase-3-protocol-transfer.json").write_text(json.dumps(phase3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    phase4 = {
        "phase_name": "teacher_selection",
        "status": "ready",
        "teacher_kind": teacher_kind,
        "teacher_basis": "highest arousal_coarse macro_f1 on real_label_finetune",
        "runner_up_kind": runner_up_kind,
        "committee_kinds": committee_kinds,
    }
    phase_reports["phase_4"] = phase4
    (output_root / "phase-4-teacher-selection.json").write_text(json.dumps(phase4, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pseudo_candidates = _build_pseudo_label_candidate_pool(
        examples_by_dataset=examples_by_dataset,
        primary_dataset_key=real_key,
    )
    accepted_pseudo_rows = _generate_pseudo_labels_with_agreement(
        examples=pseudo_candidates,
        feature_names=real_feature_names,
        committee_models=committee_models,
        min_votes=max(2, len(committee_models) // 2 + 1),
    )
    pre_guardrail_count = len(accepted_pseudo_rows)
    accepted_pseudo_rows, guardrail_report = _apply_pseudo_label_guardrails(
        rows=accepted_pseudo_rows,
        candidate_count=len(pseudo_candidates),
        max_acceptance_rate=0.6,
        max_class_share=0.75,
        single_class_max_keep=25,
    )
    phase5 = {
        "phase_name": "pseudo_label_generation",
        "status": "ready",
        "candidate_count": len(pseudo_candidates),
        "pre_guardrail_count": pre_guardrail_count,
        "accepted_count": len(accepted_pseudo_rows),
        "acceptance_rate": round(float(len(accepted_pseudo_rows) / len(pseudo_candidates)), 6) if pseudo_candidates else 0.0,
        "selection_rule": f"committee consensus votes>={max(2, len(committee_models) // 2 + 1)} of {len(committee_models)}",
        "guardrails": guardrail_report,
    }
    phase_reports["phase_5"] = phase5
    (output_root / "phase-5-pseudo-label-generation.json").write_text(json.dumps(phase5, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_root / "phase-5-pseudo-labels.csv", _pseudo_rows_for_csv(accepted_pseudo_rows))

    phase6 = _run_phase_self_training_refit(
        teacher_kind=teacher_kind,
        feature_names=real_feature_names,
        real_train=real_train,
        real_test=real_test,
        accepted_pseudo_rows=accepted_pseudo_rows,
        max_pseudo_ratio=0.5,
    )
    phase_reports["phase_6"] = phase6
    (output_root / "phase-6-self-training-refit.json").write_text(json.dumps(_drop_models(phase6), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    phase7 = _run_phase_cross_dataset_eval(
        examples_by_dataset=examples_by_dataset,
        feature_names=real_feature_names,
        supervised_model=teacher_model,
        self_trained_model=phase6["self_trained_model"],
        teacher_kind=teacher_kind,
    )
    phase_reports["phase_7"] = phase7
    (output_root / "phase-7-cross-dataset-evaluation.json").write_text(json.dumps(_drop_models(phase7), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    promote = bool(
        phase6["self_training_metrics"]["macro_f1"] > phase6["supervised_metrics"]["macro_f1"]
        and phase6["delta_macro_f1"] > 0.0
    )
    phase8 = {
        "phase_name": "model_freeze_decision",
        "status": "ready",
        "decision": "promote_self_trained" if promote else "keep_supervised_baseline",
        "promotion_rule": "promote only if real-label arousal macro_f1 strictly improves",
        "delta_macro_f1": phase6["delta_macro_f1"],
    }
    phase_reports["phase_8"] = phase8
    (output_root / "phase-8-model-freeze-decision.json").write_text(json.dumps(phase8, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    comparison_rows = _build_execution_comparison_rows(phase1, phase2, phase3, _drop_models(phase7))
    _write_csv(output_root / "model-comparison.csv", comparison_rows)
    _write_csv(output_root / "phase-execution.csv", self_training_phases)

    experiment_id = f"g3-2-self-training-execution-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report = {
        "experiment_id": experiment_id,
        "execution_scope": "Execute end-to-end multi-dataset self-training phases (0-8).",
        "overall_status": "completed",
        "dataset_strategy": dataset_rows,
        "phase_reports": _drop_models(phase_reports),
        "phase_execution": self_training_phases,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    report_path = output_root / "self-training-execution-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    research_report_path = output_root / "research-report.md"
    research_report_path.write_text(_build_self_training_execution_md(report), encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "phase_execution_path": str(output_root / "phase-execution.csv"),
        "model_comparison_path": str(output_root / "model-comparison.csv"),
        "research_report_path": str(research_report_path),
        "overall_status": "completed",
        "decision": phase8["decision"],
    }


def _fit_predict(kind: str, x_train: np.ndarray, y_train: list[str], x_test: np.ndarray) -> list[str]:
    if kind == "centroid":
        model = CentroidClassifier()
    elif kind == "gaussian_nb":
        model = GaussianNBClassifier()
    else:
        model = build_estimator_classifier(kind)
    model.fit(x_train, y_train)
    return model.predict(x_test)


def _build_dataset_strategy_rows(
    artifacts_root: Path,
    registry_path: Path,
    min_confidence: float,
) -> list[dict[str, Any]]:
    registry_rows = _load_jsonl(registry_path)
    dataset_rows: list[dict[str, Any]] = []
    for record in sorted(registry_rows, key=lambda item: (str(item.get("dataset_id", "")), str(item.get("dataset_version", "")))):
        stats = _collect_dataset_strategy_stats(
            artifacts_root=artifacts_root,
            dataset_id=str(record.get("dataset_id", "")),
            dataset_version=str(record.get("dataset_version", "")),
            min_confidence=min_confidence,
        )
        label_quality = _classify_arousal_label_quality(record)
        recommended_role = _recommended_arousal_role(
            label_quality=label_quality,
            coverage_status=str(stats["coverage_status"]),
        )
        dataset_rows.append(
            {
                "dataset_id": str(record.get("dataset_id", "")),
                "dataset_version": str(record.get("dataset_version", "")),
                "target_tracks": ",".join(record.get("target_tracks", [])),
                "labels_available": ",".join(record.get("labels_available", [])),
                "modalities_available": ",".join(record.get("modalities_available", [])),
                "label_quality_tier": label_quality,
                "recommended_role": recommended_role,
                **stats,
            }
        )
    return dataset_rows


def _collect_dataset_strategy_stats(
    artifacts_root: Path,
    dataset_id: str,
    dataset_version: str,
    min_confidence: float,
) -> dict[str, Any]:
    feature_context = _new_signal_feature_context(artifacts_root)
    dataset_root = _resolve_dataset_root(artifacts_root, dataset_id, dataset_version)
    labels_path = dataset_root / "unified" / "segment-labels.jsonl"
    split_path = dataset_root / "manifest" / "split-manifest.json"
    if not labels_path.exists() or not split_path.exists():
        return {
            "coverage_status": "missing_artifacts",
            "eligible_segments": 0,
            "subject_count_filtered": 0,
            "train_segments": 0,
            "validation_segments": 0,
            "test_segments": 0,
            "train_subjects": 0,
            "validation_subjects": 0,
            "test_subjects": 0,
            "activity_class_count": 0,
            "arousal_class_count": 0,
            "arousal_train_class_count": 0,
            "arousal_test_class_count": 0,
            "arousal_class_distribution": "",
            "label_source_types": "",
            "harmonized_feature_count": 0,
        }

    labels = _load_jsonl(labels_path)
    split_manifest = _load_json(split_path)
    examples = _build_examples(
        labels=labels,
        split_manifest=split_manifest,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        min_confidence=min_confidence,
        feature_context=feature_context,
    )
    train = [item for item in examples if item.split == "train"]
    validation = [item for item in examples if item.split == "validation"]
    test = [item for item in examples if item.split == "test"]

    filtered_rows = [
        row
        for row in labels
        if row.get("dataset_id") == dataset_id
        and row.get("dataset_version") == dataset_version
        and float(row.get("confidence", 0.0)) >= min_confidence
        and str(row.get("activity_label", "unknown")) != "unknown"
    ]
    label_source_counts = Counter(str(row.get("source", "")) for row in filtered_rows)
    arousal_counts = Counter(item.arousal_coarse for item in examples)
    harmonized_feature_names = sorted({name for item in examples for name in item.features.keys()})

    coverage_status = "ready"
    if not train or not test:
        coverage_status = "insufficient_train_test"
    elif len({item.arousal_coarse for item in train}) < 2 or len({item.arousal_coarse for item in test}) < 2:
        coverage_status = "insufficient_arousal_class_coverage"

    return {
        "coverage_status": coverage_status,
        "eligible_segments": len(examples),
        "subject_count_filtered": len({item.subject_id for item in examples}),
        "train_segments": len(train),
        "validation_segments": len(validation),
        "test_segments": len(test),
        "train_subjects": len({item.subject_id for item in train}),
        "validation_subjects": len({item.subject_id for item in validation}),
        "test_subjects": len({item.subject_id for item in test}),
        "activity_class_count": len({item.activity_label for item in examples}),
        "arousal_class_count": len(arousal_counts),
        "arousal_train_class_count": len({item.arousal_coarse for item in train}),
        "arousal_test_class_count": len({item.arousal_coarse for item in test}),
        "arousal_class_distribution": ",".join(
            f"{label}:{count}"
            for label, count in sorted(arousal_counts.items())
        ),
        "label_source_types": ",".join(
            f"{label}:{count}"
            for label, count in sorted(label_source_counts.items())
        ),
        "harmonized_feature_count": len(harmonized_feature_names),
    }


def _classify_arousal_label_quality(record: dict[str, Any]) -> str:
    dataset_id = str(record.get("dataset_id", ""))
    target_tracks = {str(item) for item in record.get("target_tracks", [])}
    labels_available = {str(item) for item in record.get("labels_available", [])}

    if "arousal_proxy" in target_tracks or any(item.endswith("_proxy") for item in labels_available):
        return "proxy_label"
    if dataset_id in PROTOCOL_MAPPED_AROUSAL_DATASETS:
        return "protocol_state_mapped"
    if dataset_id in PRIMARY_AROUSAL_DATASETS or "arousal_1to5" in labels_available:
        return "real_annotation_mapped"
    if "arousal" in target_tracks:
        return "mapped_label_unknown_grade"
    return "no_arousal_track"


def _recommended_arousal_role(label_quality: str, coverage_status: str) -> str:
    if coverage_status != "ready":
        return "skip"
    if label_quality == "real_annotation_mapped":
        return "primary_supervision"
    if label_quality == "protocol_state_mapped":
        return "protocol_transfer_or_eval"
    if label_quality == "proxy_label":
        return "auxiliary_pretraining"
    if label_quality == "mapped_label_unknown_grade":
        return "holdout_eval_only"
    return "skip"


def _build_training_phases(dataset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    phase_specs = [
        (
            "phase_1",
            "proxy_pretraining",
            "auxiliary_pretraining",
            "Learn shared signal representations or auxiliary heads on proxy datasets only.",
            "Do not use this phase for headline arousal claims.",
        ),
        (
            "phase_2",
            "real_label_finetune",
            "primary_supervision",
            "Fine-tune and select the main arousal model on real-label datasets.",
            "This is the only phase allowed to drive headline model selection.",
        ),
        (
            "phase_3",
            "protocol_transfer",
            "protocol_transfer_or_eval",
            "Use protocol-mapped datasets for transfer diagnostics or separate adaptation experiments.",
            "Keep protocol-derived results outside claim-grade pooled metrics.",
        ),
        (
            "phase_4",
            "cross_dataset_evaluation",
            "evaluation",
            "Run per-dataset evaluation without collapsing real, protocol, and proxy labels into one claim.",
            "Report each dataset family separately.",
        ),
    ]

    for phase_id, phase_name, role_name, objective, guardrail in phase_specs:
        if role_name == "evaluation":
            datasets = [
                f"{row['dataset_id']}:{row['dataset_version']}"
                for row in dataset_rows
                if row["coverage_status"] == "ready"
            ]
        else:
            datasets = [
                f"{row['dataset_id']}:{row['dataset_version']}"
                for row in dataset_rows
                if row["recommended_role"] == role_name
            ]
        if not datasets:
            continue
        phases.append(
            {
                "phase_id": phase_id,
                "phase_name": phase_name,
                "datasets": ",".join(datasets),
                "objective": objective,
                "guardrail": guardrail,
            }
        )
    return phases


def _build_protocol_readiness_rows(dataset_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in dataset_rows:
        dataset_key = f"{row['dataset_id']}:{row['dataset_version']}"
        role = row["recommended_role"]
        coverage_status = row["coverage_status"]
        if role == "skip":
            rows.append(
                {
                    "dataset": dataset_key,
                    "check": "dataset_coverage",
                    "status": "skipped",
                    "detail": f"coverage_status={coverage_status}",
                }
            )
            continue

        rows.append(
            {
                "dataset": dataset_key,
                "check": "dataset_coverage",
                "status": "passed" if coverage_status == "ready" else "failed",
                "detail": f"coverage_status={coverage_status}",
            }
        )
        rows.append(
            {
                "dataset": dataset_key,
                "check": "harmonized_signal_features",
                "status": "passed" if int(row.get("harmonized_feature_count", 0)) > 0 else "failed",
                "detail": (
                    f"harmonized_feature_count={int(row.get('harmonized_feature_count', 0))}"
                    if int(row.get("harmonized_feature_count", 0)) > 0
                    else "current multi-dataset pipeline has no harmonized non-label features"
                ),
            }
        )
    return rows


def _build_phase_execution_rows(
    training_phases: list[dict[str, Any]],
    readiness_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures_by_dataset: dict[str, list[str]] = {}
    for row in readiness_rows:
        if row["status"] != "failed":
            continue
        failures_by_dataset.setdefault(str(row["dataset"]), []).append(str(row["check"]))

    phase_rows: list[dict[str, Any]] = []
    for phase in training_phases:
        datasets = [item.strip() for item in str(phase["datasets"]).split(",") if item.strip()]
        blockers = []
        for dataset in datasets:
            checks = failures_by_dataset.get(dataset, [])
            blockers.extend(f"{dataset}:{check}" for check in checks)
        if blockers:
            status = "blocked"
            detail = "; ".join(sorted(set(blockers)))
        else:
            status = "ready"
            detail = "all required checks passed"
        phase_rows.append(
            {
                "phase_id": phase["phase_id"],
                "phase_name": phase["phase_name"],
                "datasets": phase["datasets"],
                "status": status,
                "detail": detail,
            }
        )
    return phase_rows


def _build_self_training_phase_rows(
    protocol_phase_rows: list[dict[str, Any]],
    readiness_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    protocol_status = {str(row["phase_name"]): str(row["status"]) for row in protocol_phase_rows}
    has_failed_readiness = any(row["status"] == "failed" for row in readiness_rows)

    phase_specs = [
        (
            "phase_0",
            "freeze_gates",
            "Freeze safe baseline and confirm protocol readiness before training.",
            "none",
            [] if not has_failed_readiness else ["readiness_checks"],
        ),
        (
            "phase_1",
            "proxy_pretraining",
            "Train proxy representation branch on auxiliary datasets.",
            "emowear:proxy",
            [] if protocol_status.get("proxy_pretraining") == "ready" and not has_failed_readiness else ["protocol:proxy_pretraining"],
        ),
        (
            "phase_2",
            "real_label_finetune",
            "Fine-tune headline model on real-label dataset.",
            "grex:real",
            [] if protocol_status.get("real_label_finetune") == "ready" and not has_failed_readiness else ["protocol:real_label_finetune"],
        ),
        (
            "phase_3",
            "protocol_transfer",
            "Run transfer diagnostics on protocol-mapped dataset.",
            "wesad:protocol_mapped",
            [] if protocol_status.get("protocol_transfer") == "ready" and not has_failed_readiness else ["protocol:protocol_transfer"],
        ),
        (
            "phase_4",
            "teacher_selection",
            "Select teacher candidate from real-label winners with calibration checks.",
            "grex:real",
            [] if protocol_status.get("real_label_finetune") == "ready" and not has_failed_readiness else ["upstream:real_label_finetune"],
        ),
        (
            "phase_5",
            "pseudo_label_generation",
            "Generate pseudo-labels only for high-confidence unlabeled segments.",
            "cross_dataset_unlabeled_pool",
            [] if protocol_status.get("real_label_finetune") == "ready" and not has_failed_readiness else ["upstream:teacher_selection"],
        ),
        (
            "phase_6",
            "self_training_refit",
            "Refit student model with weighted real+pseudo labels.",
            "grex_plus_pseudo",
            [] if protocol_status.get("real_label_finetune") == "ready" and not has_failed_readiness else ["upstream:pseudo_label_generation"],
        ),
        (
            "phase_7",
            "cross_dataset_evaluation",
            "Evaluate supervised and self-trained branches on all ready datasets.",
            "emowear,grex,wesad",
            [] if protocol_status.get("cross_dataset_evaluation") == "ready" and not has_failed_readiness else ["protocol:cross_dataset_evaluation"],
        ),
        (
            "phase_8",
            "model_freeze_decision",
            "Freeze candidate only if real-label and guardrail criteria pass.",
            "decision_gate",
            [] if protocol_status.get("cross_dataset_evaluation") == "ready" and not has_failed_readiness else ["upstream:cross_dataset_evaluation"],
        ),
    ]

    rows: list[dict[str, Any]] = []
    previous_blocked = False
    for phase_id, phase_name, objective, dataset_scope, blockers in phase_specs:
        if previous_blocked:
            blockers = blockers + ["upstream:blocking_phase"]
        status = "ready" if not blockers else "blocked"
        previous_blocked = previous_blocked or status == "blocked"
        rows.append(
            {
                "phase_id": phase_id,
                "phase_name": phase_name,
                "dataset_scope": dataset_scope,
                "status": status,
                "objective": objective,
                "blockers": ",".join(sorted(set(blockers))) if blockers else "",
            }
        )
    return rows


def _build_self_training_metrics_contract() -> list[dict[str, Any]]:
    return [
        {"phase_name": "proxy_pretraining", "track": "activity", "metric_name": "macro_f1", "metric_role": "diagnostic"},
        {"phase_name": "proxy_pretraining", "track": "arousal_coarse", "metric_name": "balanced_accuracy", "metric_role": "diagnostic"},
        {"phase_name": "proxy_pretraining", "track": "arousal_coarse", "metric_name": "log_loss", "metric_role": "diagnostic"},
        {"phase_name": "real_label_finetune", "track": "activity", "metric_name": "macro_f1", "metric_role": "headline"},
        {"phase_name": "real_label_finetune", "track": "arousal_coarse", "metric_name": "macro_f1", "metric_role": "headline"},
        {"phase_name": "real_label_finetune", "track": "arousal_coarse", "metric_name": "balanced_accuracy", "metric_role": "headline"},
        {"phase_name": "real_label_finetune", "track": "arousal_coarse", "metric_name": "quadratic_weighted_kappa", "metric_role": "headline"},
        {"phase_name": "protocol_transfer", "track": "arousal_coarse", "metric_name": "macro_f1", "metric_role": "transfer_diagnostic"},
        {"phase_name": "teacher_selection", "track": "arousal_coarse", "metric_name": "ece", "metric_role": "selection_gate"},
        {"phase_name": "teacher_selection", "track": "arousal_coarse", "metric_name": "confidence_entropy", "metric_role": "selection_gate"},
        {"phase_name": "pseudo_label_generation", "track": "arousal_coarse", "metric_name": "accepted_fraction", "metric_role": "quality_gate"},
        {"phase_name": "pseudo_label_generation", "track": "arousal_coarse", "metric_name": "mean_confidence", "metric_role": "quality_gate"},
        {"phase_name": "self_training_refit", "track": "arousal_coarse", "metric_name": "macro_f1_delta_vs_supervised", "metric_role": "promotion_gate"},
        {"phase_name": "self_training_refit", "track": "arousal_coarse", "metric_name": "worst_subject_delta", "metric_role": "guardrail"},
        {"phase_name": "cross_dataset_evaluation", "track": "activity", "metric_name": "macro_f1", "metric_role": "reporting"},
        {"phase_name": "cross_dataset_evaluation", "track": "arousal_coarse", "metric_name": "macro_f1", "metric_role": "reporting"},
        {"phase_name": "model_freeze_decision", "track": "arousal_coarse", "metric_name": "promotion_decision", "metric_role": "final_gate"},
    ]


def _load_ready_dataset_examples_by_split(
    artifacts_root: Path,
    dataset_rows: list[dict[str, Any]],
    min_confidence: float,
) -> dict[str, dict[str, Any]]:
    feature_context = _new_signal_feature_context(artifacts_root)
    bundles: dict[str, dict[str, Any]] = {}
    for row in dataset_rows:
        if row.get("coverage_status") != "ready":
            continue
        dataset_id = str(row["dataset_id"])
        dataset_version = str(row["dataset_version"])
        dataset_key = f"{dataset_id}:{dataset_version}"
        dataset_root = _resolve_dataset_root(artifacts_root, dataset_id, dataset_version)
        labels_path = dataset_root / "unified" / "segment-labels.jsonl"
        split_path = dataset_root / "manifest" / "split-manifest.json"
        labels = _load_jsonl(labels_path)
        split_manifest = _load_json(split_path)
        examples = _build_examples(
            labels=labels,
            split_manifest=split_manifest,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            min_confidence=min_confidence,
            feature_context=feature_context,
        )
        bundles[dataset_key] = {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "examples": examples,
            "train": [item for item in examples if item.split == "train"],
            "validation": [item for item in examples if item.split == "validation"],
            "test": [item for item in examples if item.split == "test"],
            "feature_names": sorted({name for item in examples for name in item.features.keys()}),
        }
    return bundles


def _first_dataset_key_by_role(dataset_rows: list[dict[str, Any]], role: str) -> str | None:
    for row in dataset_rows:
        if row.get("recommended_role") != role:
            continue
        if row.get("coverage_status") != "ready":
            continue
        return f"{row['dataset_id']}:{row['dataset_version']}"
    return None


def _run_phase_train_eval(
    phase_name: str,
    dataset_key: str,
    candidate_kinds: list[str],
    examples_by_dataset: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    bundle = examples_by_dataset[dataset_key]
    train = bundle["train"]
    test = bundle["test"]
    feature_names = _select_safe_feature_names(sorted(bundle["feature_names"]))
    if not train or not test:
        return {"phase_name": phase_name, "status": "blocked", "reason": "insufficient train/test examples"}

    x_train = _to_matrix(train, feature_names)
    x_test = _to_matrix(test, feature_names)
    activity_train = [item.activity_label for item in train]
    activity_test = [item.activity_label for item in test]
    arousal_train = [item.arousal_coarse for item in train]
    arousal_test = [item.arousal_coarse for item in test]

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for kind in candidate_kinds:
        try:
            activity_pred = _fit_predict(kind, x_train, activity_train, x_test)
            activity_metrics = compute_classification_metrics(activity_test, activity_pred)
            rows.append(
                {
                    "phase_name": phase_name,
                    "dataset": dataset_key,
                    "kind": kind,
                    "track": "activity",
                    "macro_f1": activity_metrics.macro_f1,
                    "balanced_accuracy": activity_metrics.balanced_accuracy,
                }
            )
        except Exception as exc:
            failures.append({"kind": kind, "track": "activity", "error_type": type(exc).__name__, "error_message": str(exc)})
        try:
            arousal_pred = _fit_predict(kind, x_train, arousal_train, x_test)
            arousal_metrics = compute_classification_metrics(arousal_test, arousal_pred)
            rows.append(
                {
                    "phase_name": phase_name,
                    "dataset": dataset_key,
                    "kind": kind,
                    "track": "arousal_coarse",
                    "macro_f1": arousal_metrics.macro_f1,
                    "balanced_accuracy": arousal_metrics.balanced_accuracy,
                }
            )
        except Exception as exc:
            failures.append({"kind": kind, "track": "arousal_coarse", "error_type": type(exc).__name__, "error_message": str(exc)})

    arousal_rows = [row for row in rows if row["track"] == "arousal_coarse"]
    arousal_sorted = sorted(arousal_rows, key=lambda item: float(item["macro_f1"]), reverse=True)
    winner_kind = arousal_sorted[0]["kind"] if arousal_sorted else None
    runner_up_kind = arousal_sorted[1]["kind"] if len(arousal_sorted) > 1 else winner_kind
    top_arousal_kinds = [row["kind"] for row in arousal_sorted]
    return {
        "phase_name": phase_name,
        "status": "ready" if rows else "blocked",
        "dataset": dataset_key,
        "feature_count": len(feature_names),
        "rows": rows,
        "failed_candidates": failures,
        "winner_arousal_kind": winner_kind,
        "runner_up_arousal_kind": runner_up_kind,
        "top_arousal_kinds": top_arousal_kinds,
    }


def _fit_model(kind: str, x_train: np.ndarray, y_train: list[str]) -> Any:
    if kind == "centroid":
        model = CentroidClassifier()
    elif kind == "gaussian_nb":
        model = GaussianNBClassifier()
    else:
        model = build_estimator_classifier(kind)
    model.fit(x_train, y_train)
    return model


def _predict_model(model: Any, x_test: np.ndarray) -> list[str]:
    return list(model.predict(x_test))


def _run_phase_transfer_eval(
    phase_name: str,
    dataset_key: str,
    model_kind: str,
    model: Any,
    feature_names: list[str],
    examples_by_dataset: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    bundle = examples_by_dataset[dataset_key]
    test = bundle["test"]
    if not test:
        return {"phase_name": phase_name, "status": "blocked", "reason": "missing test split", "dataset": dataset_key}
    x_test = _to_matrix(test, feature_names)
    y_test = [item.arousal_coarse for item in test]
    pred = _predict_model(model, x_test)
    metrics = compute_classification_metrics(y_test, pred)
    return {
        "phase_name": phase_name,
        "status": "ready",
        "dataset": dataset_key,
        "model_kind": model_kind,
        "track": "arousal_coarse",
        "macro_f1": metrics.macro_f1,
        "balanced_accuracy": metrics.balanced_accuracy,
        "labels": metrics.labels,
        "confusion_matrix": metrics.confusion_matrix,
    }


def _build_pseudo_label_candidate_pool(
    examples_by_dataset: dict[str, dict[str, Any]],
    primary_dataset_key: str,
) -> list[Example]:
    pool: list[Example] = []
    for dataset_key, bundle in examples_by_dataset.items():
        if dataset_key == primary_dataset_key:
            continue
        for item in bundle["train"] + bundle["validation"]:
            pool.append(item)
    return pool


def _generate_pseudo_labels_with_agreement(
    examples: list[Example],
    feature_names: list[str],
    committee_models: dict[str, Any],
    min_votes: int,
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    if not committee_models:
        return accepted
    min_votes = max(1, min(min_votes, len(committee_models)))
    for item in examples:
        x_row = _to_matrix([item], feature_names)
        votes: Counter[str] = Counter()
        for model in committee_models.values():
            votes[_predict_model(model, x_row)[0]] += 1
        label, count = votes.most_common(1)[0]
        if count < min_votes:
            continue
        feature_values = x_row.reshape(-1).tolist()
        accepted.append(
            {
                "dataset_id": item.dataset_id,
                "dataset_version": item.dataset_version,
                "subject_id": item.subject_id,
                "session_id": item.session_id,
                "segment_id": item.segment_id,
                "pseudo_arousal_coarse": label,
                "agreement_rule": f"committee_vote_{count}_of_{len(committee_models)}",
                "vote_count": int(count),
                "feature_values": feature_values,
            }
        )
    return accepted


def _apply_pseudo_label_guardrails(
    rows: list[dict[str, Any]],
    candidate_count: int,
    max_acceptance_rate: float,
    max_class_share: float,
    single_class_max_keep: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not rows or candidate_count <= 0:
        return [], {
            "max_acceptance_rate": max_acceptance_rate,
            "max_class_share": max_class_share,
            "single_class_max_keep": single_class_max_keep,
            "applied": False,
            "reason": "empty_candidates_or_votes",
        }

    max_acceptance_rate = min(max(max_acceptance_rate, 0.0), 1.0)
    max_class_share = min(max(max_class_share, 0.0), 1.0)
    hard_cap = max(1, int(candidate_count * max_acceptance_rate))

    ranked = sorted(
        rows,
        key=lambda item: (
            -int(item.get("vote_count", 0)),
            str(item.get("dataset_id", "")),
            str(item.get("subject_id", "")),
            str(item.get("segment_id", "")),
        ),
    )
    trimmed = ranked[:hard_cap]

    class_counts = Counter(str(item.get("pseudo_arousal_coarse", "")) for item in trimmed)
    class_limit = max(1, int(len(trimmed) * max_class_share))
    filtered: list[dict[str, Any]] = []
    class_kept: Counter[str] = Counter()
    for item in trimmed:
        label = str(item.get("pseudo_arousal_coarse", ""))
        if class_kept[label] >= class_limit:
            continue
        filtered.append(item)
        class_kept[label] += 1

    filtered_counts = Counter(str(item.get("pseudo_arousal_coarse", "")) for item in filtered)
    if len(filtered_counts) == 1 and len(filtered) > single_class_max_keep:
        filtered = filtered[:single_class_max_keep]
        filtered_counts = Counter(str(item.get("pseudo_arousal_coarse", "")) for item in filtered)

    return filtered, {
        "max_acceptance_rate": max_acceptance_rate,
        "max_class_share": max_class_share,
        "single_class_max_keep": single_class_max_keep,
        "hard_cap": hard_cap,
        "class_limit": class_limit,
        "before_count": len(rows),
        "after_count": len(filtered),
        "before_class_distribution": dict(class_counts),
        "after_class_distribution": dict(filtered_counts),
        "applied": True,
    }


def _run_phase_self_training_refit(
    teacher_kind: str,
    feature_names: list[str],
    real_train: list[Example],
    real_test: list[Example],
    accepted_pseudo_rows: list[dict[str, Any]],
    max_pseudo_ratio: float,
) -> dict[str, Any]:
    x_real_train = _to_matrix(real_train, feature_names)
    y_real_train = [item.arousal_coarse for item in real_train]
    x_real_test = _to_matrix(real_test, feature_names)
    y_real_test = [item.arousal_coarse for item in real_test]

    supervised_model = _fit_model(teacher_kind, x_real_train, y_real_train)
    supervised_pred = _predict_model(supervised_model, x_real_test)
    supervised_metrics = compute_classification_metrics(y_real_test, supervised_pred)

    pseudo_cap = int(max(0.0, max_pseudo_ratio) * len(real_train))
    selected_pseudo = accepted_pseudo_rows[:pseudo_cap] if pseudo_cap > 0 else []
    x_pseudo = (
        np.asarray([row["feature_values"] for row in selected_pseudo], dtype=float)
        if selected_pseudo
        else np.zeros((0, len(feature_names)), dtype=float)
    )
    y_pseudo = [str(row["pseudo_arousal_coarse"]) for row in selected_pseudo]

    x_aug = np.concatenate([x_real_train, x_pseudo], axis=0) if len(x_pseudo) > 0 else x_real_train
    y_aug = y_real_train + y_pseudo
    self_trained_model = _fit_model(teacher_kind, x_aug, y_aug)
    self_trained_pred = _predict_model(self_trained_model, x_real_test)
    self_trained_metrics = compute_classification_metrics(y_real_test, self_trained_pred)

    return {
        "phase_name": "self_training_refit",
        "status": "ready",
        "teacher_kind": teacher_kind,
        "pseudo_selected_count": len(selected_pseudo),
        "supervised_metrics": {
            "macro_f1": supervised_metrics.macro_f1,
            "balanced_accuracy": supervised_metrics.balanced_accuracy,
        },
        "self_training_metrics": {
            "macro_f1": self_trained_metrics.macro_f1,
            "balanced_accuracy": self_trained_metrics.balanced_accuracy,
        },
        "delta_macro_f1": round(float(self_trained_metrics.macro_f1 - supervised_metrics.macro_f1), 6),
        "self_trained_model": self_trained_model,
    }


def _pseudo_rows_for_csv(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "dataset_id": row["dataset_id"],
                "dataset_version": row["dataset_version"],
                "subject_id": row["subject_id"],
                "session_id": row["session_id"],
                "segment_id": row["segment_id"],
                "pseudo_arousal_coarse": row["pseudo_arousal_coarse"],
                "agreement_rule": row["agreement_rule"],
                "vote_count": int(row.get("vote_count", 0)),
            }
        )
    return output


def _run_phase_cross_dataset_eval(
    examples_by_dataset: dict[str, dict[str, Any]],
    feature_names: list[str],
    supervised_model: Any,
    self_trained_model: Any,
    teacher_kind: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for dataset_key, bundle in sorted(examples_by_dataset.items()):
        test = bundle["test"]
        if not test:
            continue
        x_test = _to_matrix(test, feature_names)
        y_arousal = [item.arousal_coarse for item in test]
        y_activity = [item.activity_label for item in test]

        sup_arousal_pred = _predict_model(supervised_model, x_test)
        self_arousal_pred = _predict_model(self_trained_model, x_test)
        sup_arousal_metrics = compute_classification_metrics(y_arousal, sup_arousal_pred)
        self_arousal_metrics = compute_classification_metrics(y_arousal, self_arousal_pred)
        rows.append(
            {
                "dataset": dataset_key,
                "track": "arousal_coarse",
                "model_variant": f"{teacher_kind}_supervised",
                "macro_f1": sup_arousal_metrics.macro_f1,
                "balanced_accuracy": sup_arousal_metrics.balanced_accuracy,
            }
        )
        rows.append(
            {
                "dataset": dataset_key,
                "track": "arousal_coarse",
                "model_variant": f"{teacher_kind}_self_trained",
                "macro_f1": self_arousal_metrics.macro_f1,
                "balanced_accuracy": self_arousal_metrics.balanced_accuracy,
            }
        )

        sup_activity_pred = _predict_model(supervised_model, x_test)
        self_activity_pred = _predict_model(self_trained_model, x_test)
        sup_activity_metrics = compute_classification_metrics(y_activity, sup_activity_pred)
        self_activity_metrics = compute_classification_metrics(y_activity, self_activity_pred)
        rows.append(
            {
                "dataset": dataset_key,
                "track": "activity",
                "model_variant": f"{teacher_kind}_supervised",
                "macro_f1": sup_activity_metrics.macro_f1,
                "balanced_accuracy": sup_activity_metrics.balanced_accuracy,
            }
        )
        rows.append(
            {
                "dataset": dataset_key,
                "track": "activity",
                "model_variant": f"{teacher_kind}_self_trained",
                "macro_f1": self_activity_metrics.macro_f1,
                "balanced_accuracy": self_activity_metrics.balanced_accuracy,
            }
        )
    return {
        "phase_name": "cross_dataset_evaluation",
        "status": "ready",
        "teacher_kind": teacher_kind,
        "rows": rows,
        "supervised_model": supervised_model,
        "self_trained_model": self_trained_model,
    }


def _drop_models(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _drop_models(value) for key, value in payload.items() if key not in {"supervised_model", "self_trained_model"}}
    if isinstance(payload, list):
        return [_drop_models(item) for item in payload]
    return payload


def _build_execution_comparison_rows(
    phase1: dict[str, Any],
    phase2: dict[str, Any],
    phase3: dict[str, Any],
    phase7: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase in (phase1, phase2):
        for item in phase.get("rows", []):
            rows.append(
                {
                    "phase_name": phase["phase_name"],
                    "dataset": item["dataset"],
                    "kind": item["kind"],
                    "track": item["track"],
                    "macro_f1": item["macro_f1"],
                    "balanced_accuracy": item["balanced_accuracy"],
                }
            )
    if phase3.get("status") == "ready":
        rows.append(
            {
                "phase_name": phase3["phase_name"],
                "dataset": phase3["dataset"],
                "kind": phase3["model_kind"],
                "track": phase3["track"],
                "macro_f1": phase3["macro_f1"],
                "balanced_accuracy": phase3["balanced_accuracy"],
            }
        )
    for item in phase7.get("rows", []):
        rows.append(
            {
                "phase_name": "cross_dataset_evaluation",
                "dataset": item["dataset"],
                "kind": item["model_variant"],
                "track": item["track"],
                "macro_f1": item["macro_f1"],
                "balanced_accuracy": item["balanced_accuracy"],
            }
        )
    return rows


def _resolve_dataset_root(artifacts_root: Path, dataset_id: str, dataset_version: str) -> Path:
    direct = artifacts_root / dataset_id / dataset_version
    nested = artifacts_root / dataset_id / "artifacts" / dataset_id / dataset_version
    if (direct / "unified" / "segment-labels.jsonl").exists():
        return direct
    if (nested / "unified" / "segment-labels.jsonl").exists():
        return nested
    # Fallback keeps previous behavior for easier debugging.
    return direct


def _build_examples(
    labels: list[dict[str, Any]],
    split_manifest: dict[str, Any],
    dataset_id: str,
    dataset_version: str,
    min_confidence: float,
    feature_context: _SignalFeatureContext,
) -> list[Example]:
    split_index: dict[str, str] = {}
    for item in split_manifest.get("train_subject_ids", []):
        split_index[str(item)] = "train"
    for item in split_manifest.get("validation_subject_ids", []):
        split_index[str(item)] = "validation"
    for item in split_manifest.get("test_subject_ids", []):
        split_index[str(item)] = "test"

    rows: list[Example] = []
    for row in labels:
        if row.get("dataset_id") != dataset_id or row.get("dataset_version") != dataset_version:
            continue
        if float(row.get("confidence", 0.0)) < min_confidence:
            continue
        activity_label = str(row.get("activity_label", "unknown"))
        if activity_label == "unknown":
            continue

        session_id = str(row["session_id"])
        subject_token = _subject_token_from_session_id(session_id)
        if subject_token is None:
            continue
        subject_id = f"{dataset_id}:{subject_token}"
        split = split_index.get(subject_id)
        if split is None:
            continue

        arousal_score = int(row.get("arousal_score", 5))
        arousal_coarse = "low" if arousal_score <= 3 else "medium" if arousal_score <= 6 else "high"

        sample_count = row.get("source_sample_count")
        if sample_count is None:
            start_idx = row.get("source_segment_start_index")
            end_idx = row.get("source_segment_end_index")
            if start_idx is not None and end_idx is not None:
                sample_count = int(end_idx) - int(start_idx) + 1
            else:
                sample_count = 0
        sample_count = max(int(sample_count), 0)

        features = _harmonized_signal_features(
            dataset_id=dataset_id,
            row=row,
            subject_token=subject_token,
            segment_id=str(row["segment_id"]),
            feature_context=feature_context,
        )
        if not features:
            continue

        rows.append(
            Example(
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                subject_id=subject_id,
                session_id=session_id,
                segment_id=str(row["segment_id"]),
                split=split,
                activity_label=activity_label,
                arousal_coarse=arousal_coarse,
                features=features,
            )
        )

    return rows


def _new_signal_feature_context(artifacts_root: Path) -> _SignalFeatureContext:
    return _SignalFeatureContext(
        artifacts_root=artifacts_root,
        wesad_streams_cache={},
        grex_payload=None,
        emowear_feature_cache={},
    )


def _harmonized_signal_features(
    dataset_id: str,
    row: dict[str, Any],
    subject_token: str,
    segment_id: str,
    feature_context: _SignalFeatureContext,
) -> dict[str, float]:
    if dataset_id == "wesad":
        return _wesad_signal_features(row=row, subject_token=subject_token, feature_context=feature_context)
    if dataset_id == "grex":
        return _grex_signal_features(segment_id=segment_id, feature_context=feature_context)
    if dataset_id == "emowear":
        return _emowear_signal_features(row=row, subject_token=subject_token, feature_context=feature_context)
    return {}


def _wesad_signal_features(
    row: dict[str, Any],
    subject_token: str,
    feature_context: _SignalFeatureContext,
) -> dict[str, float]:
    start = row.get("source_segment_start_index")
    end = row.get("source_segment_end_index")
    if start is None or end is None:
        return {}
    raw_root = feature_context.artifacts_root / "wesad" / "raw"
    if not raw_root.exists():
        return {}
    streams = feature_context.wesad_streams_cache.get(subject_token)
    if streams is None:
        try:
            streams = _load_wesad_streams(raw_root=raw_root, subject_code=subject_token)
        except Exception:
            return {}
        feature_context.wesad_streams_cache[subject_token] = streams

    try:
        full = _extract_multimodal_features(
            streams=streams,
            start_index=int(start),
            end_index=int(end),
        )
    except Exception:
        return {}
    return _select_safe_feature_names_map(full)


def _grex_signal_features(
    segment_id: str,
    feature_context: _SignalFeatureContext,
) -> dict[str, float]:
    if feature_context.grex_payload is None:
        payload_path = feature_context.artifacts_root / "grex" / "raw" / "3_Physio" / "Transformed" / "physio_trans_data_segments.pickle"
        if not payload_path.exists():
            return {}
        try:
            with payload_path.open("rb") as handle:
                raw_payload = pickle.load(handle)
        except Exception:
            return {}
        if not isinstance(raw_payload, dict):
            return {}
        feature_context.grex_payload = raw_payload

    payload = feature_context.grex_payload
    if payload is None:
        return {}
    index = _segment_zero_based_index(segment_id)
    if index is None:
        return {}

    features: dict[str, float] = {}
    for key, prefix in [
        ("filt_EDA", "signal_eda"),
        ("filt_PPG", "signal_ppg"),
        ("hr", "signal_hr"),
        ("EDR", "signal_edr"),
    ]:
        values = payload.get(key)
        if not isinstance(values, list) or index >= len(values):
            continue
        arr = _as_float_vector(values[index])
        _append_stats(features, prefix, arr)
    return features


def _emowear_signal_features(
    row: dict[str, Any],
    subject_token: str,
    feature_context: _SignalFeatureContext,
) -> dict[str, float]:
    condition = str(row.get("source_label_value", ""))
    if not condition:
        return {}
    zip_path = feature_context.artifacts_root / "emowear" / "raw" / subject_token / f"{condition}.zip"
    cache_key = str(zip_path)
    if cache_key in feature_context.emowear_feature_cache:
        return dict(feature_context.emowear_feature_cache[cache_key])
    if not zip_path.exists():
        return {}

    matrix: list[list[float]] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            csv_names = [name for name in archive.namelist() if name.startswith("output_") and name.endswith(".csv")]
            if not csv_names:
                return {}
            with archive.open(csv_names[0], "r") as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", errors="replace"))
                next(reader, None)
                for row_index, raw in enumerate(reader):
                    if row_index >= 5000:
                        break
                    numeric: list[float] = []
                    for token in raw:
                        token = token.strip()
                        if not token:
                            continue
                        try:
                            value = float(token)
                        except Exception:
                            continue
                        if np.isfinite(value):
                            numeric.append(value)
                    if numeric:
                        matrix.append(numeric)
    except Exception:
        return {}
    if not matrix:
        return {}

    width = min(len(row_values) for row_values in matrix)
    trimmed = np.asarray([row_values[:width] for row_values in matrix], dtype=float)
    features: dict[str, float] = {}
    if width >= 3:
        acc = trimmed[:, :3]
        mag = np.sqrt(np.sum(acc ** 2, axis=1))
        _append_stats(features, "signal_acc_mag", mag)
    for idx in range(min(width, 6)):
        _append_stats(features, f"signal_ch{idx}", trimmed[:, idx])

    feature_context.emowear_feature_cache[cache_key] = dict(features)
    return features


def _segment_zero_based_index(segment_id: str) -> int | None:
    token = segment_id.split(":")[-1]
    digits = "".join(ch for ch in token if ch.isdigit())
    if not digits:
        return None
    index = int(digits) - 1
    if index < 0:
        return None
    return index


def _as_float_vector(values: Any) -> np.ndarray:
    try:
        arr = np.asarray(values, dtype=float).reshape(-1)
    except Exception:
        return np.asarray([], dtype=float)
    if arr.size == 0:
        return arr
    return arr[np.isfinite(arr)]


def _append_stats(features: dict[str, float], prefix: str, values: np.ndarray) -> None:
    if values.size == 0:
        return
    features[f"{prefix}__mean"] = round(float(values.mean()), 6)
    features[f"{prefix}__std"] = round(float(values.std()), 6)
    features[f"{prefix}__min"] = round(float(values.min()), 6)
    features[f"{prefix}__max"] = round(float(values.max()), 6)


def _select_safe_feature_names_map(features: dict[str, float]) -> dict[str, float]:
    safe_keys = _select_safe_feature_names(sorted(features.keys()))
    return {key: float(features[key]) for key in safe_keys}


def _subject_rows(
    dataset_id: str,
    variant_name: str,
    test_examples: list[Example],
    activity_pred: list[str] | None,
    arousal_pred: list[str] | None,
) -> list[dict[str, Any]]:
    grouped_activity: dict[str, dict[str, list[str]]] = {}
    grouped_arousal: dict[str, dict[str, list[str]]] = {}
    if activity_pred is not None:
        for item, a_pred in zip(test_examples, activity_pred):
            grouped_activity.setdefault(item.subject_id, {"true": [], "pred": []})
            grouped_activity[item.subject_id]["true"].append(item.activity_label)
            grouped_activity[item.subject_id]["pred"].append(a_pred)
    if arousal_pred is not None:
        for item, c_pred in zip(test_examples, arousal_pred):
            grouped_arousal.setdefault(item.subject_id, {"true": [], "pred": []})
            grouped_arousal[item.subject_id]["true"].append(item.arousal_coarse)
            grouped_arousal[item.subject_id]["pred"].append(c_pred)

    rows: list[dict[str, Any]] = []
    for subject_id, payload in grouped_activity.items():
        metrics = compute_classification_metrics(payload["true"], payload["pred"])
        rows.append(
            {
                "dataset_id": dataset_id,
                "variant_name": variant_name,
                "track": "activity",
                "subject_id": subject_id,
                "macro_f1": metrics.macro_f1,
                "support": len(payload["true"]),
            }
        )
    for subject_id, payload in grouped_arousal.items():
        metrics = compute_classification_metrics(payload["true"], payload["pred"])
        rows.append(
            {
                "dataset_id": dataset_id,
                "variant_name": variant_name,
                "track": "arousal_coarse",
                "subject_id": subject_id,
                "macro_f1": metrics.macro_f1,
                "support": len(payload["true"]),
            }
        )
    return rows


def _winner(rows: list[dict[str, Any]], track: str) -> dict[str, Any] | None:
    track_rows = [row for row in rows if row["track"] == track]
    if not track_rows:
        return None
    best = max(track_rows, key=lambda item: float(item["value"]))
    return {"variant_name": best["variant_name"], "value": best["value"]}


def _subject_token_from_session_id(session_id: str) -> str | None:
    parts = session_id.split(":")
    if len(parts) < 3:
        return None
    return parts[2]


def _select_safe_feature_names(all_feature_names: list[str]) -> list[str]:
    return [
        name
        for name in all_feature_names
        if not any(name.startswith(prefix) for prefix in UNSAFE_FEATURE_PREFIXES)
    ]


def _to_matrix(examples: list[Example], feature_names: list[str]) -> np.ndarray:
    matrix = np.zeros((len(examples), len(feature_names)), dtype=float)
    for r_idx, row in enumerate(examples):
        for c_idx, feature_name in enumerate(feature_names):
            matrix[r_idx, c_idx] = float(row.features.get(feature_name, 0.0))
    return matrix


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _build_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# G3.2 Multi-dataset Harmonization Benchmark",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Scope: {report['comparison_scope']}",
        f"- Benchmarked datasets: `{len(report['datasets_benchmarked'])}`",
        f"- Skipped datasets: `{len(report['skipped_datasets'])}`",
        "",
        "## Dataset Winners",
        "",
    ]
    for item in report["datasets_benchmarked"]:
        lines.append(
            f"- `{item['dataset_id']}`: activity winner=`{item['winner_activity']['variant_name']}` ({item['winner_activity']['value']})"
        )
        if item.get("winner_arousal") is not None:
            lines.append(
                f"  arousal winner=`{item['winner_arousal']['variant_name']}` ({item['winner_arousal']['value']})"
            )
    if report["skipped_datasets"]:
        lines.extend(["", "## Skipped Datasets", ""])
        for item in report["skipped_datasets"]:
            lines.append(f"- `{item['dataset_id']}:{item['dataset_version']}` -> {item['reason']}")
    lines.extend(
        [
            "",
            "## Interpretation Limits",
            "",
            "- `G3.2` no longer permits `label_*` or `meta_*` shortcut features in model inputs.",
            "- Current multi-dataset artifacts must be treated as invalid if they were produced from label/protocol metadata.",
            "- The benchmark should only resume once harmonized non-label signal features exist across datasets.",
            "- Proxy-label datasets (`emowear`, `dapper`) still require dedicated claim-grade labels before decision-gate claims.",
        ]
    )
    lines.append("")
    return "\n".join(lines)


def _build_training_protocol_md(report: dict[str, Any]) -> str:
    lines = [
        "# Multi-dataset Arousal Training Protocol",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Scope: {report['strategy_scope']}",
        "",
        "## Dataset Roles",
        "",
    ]
    for row in report["dataset_strategy"]:
        lines.append(
            f"- `{row['dataset_id']}:{row['dataset_version']}` -> "
            f"tier=`{row['label_quality_tier']}`, role=`{row['recommended_role']}`, "
            f"coverage=`{row['coverage_status']}`, arousal_dist=`{row['arousal_class_distribution']}`."
        )

    lines.extend(["", "## Recommended Phases", ""])
    for phase in report["recommended_training_phases"]:
        lines.append(f"- `{phase['phase_id']}` / `{phase['phase_name']}` -> datasets=`{phase['datasets']}`.")
        lines.append(f"  objective: {phase['objective']}")
        lines.append(f"  guardrail: {phase['guardrail']}")

    policy = report["synthetic_data_policy"]
    lines.extend(
        [
            "",
            "## Synthetic Data Policy",
            "",
            f"- allowed: `{policy['allowed']}`",
        ]
    )
    for item in policy["disallowed"]:
        lines.append(f"- disallowed: {item}")
    for item in policy["notes"]:
        lines.append(f"- note: {item}")
    lines.append("")
    return "\n".join(lines)


def _build_protocol_execution_md(report: dict[str, Any]) -> str:
    lines = [
        "# Multi-dataset Protocol Execution",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Scope: {report['execution_scope']}",
        f"- Overall status: `{report['overall_status']}`",
        "",
        "## Readiness Checks",
        "",
    ]
    for row in report["readiness_checks"]:
        lines.append(f"- `{row['dataset']}` / `{row['check']}` -> `{row['status']}` ({row['detail']}).")

    lines.extend(["", "## Phase Execution", ""])
    for row in report["phase_execution"]:
        lines.append(
            f"- `{row['phase_id']}` `{row['phase_name']}` -> `{row['status']}`; datasets=`{row['datasets']}`; {row['detail']}."
        )

    if report["blocking_phases"]:
        lines.extend(["", "## Blocking Summary", ""])
        for row in report["blocking_phases"]:
            lines.append(f"- blocked: `{row['phase_name']}` ({row['detail']})")
    lines.append("")
    return "\n".join(lines)


def _build_self_training_runbook_md(report: dict[str, Any]) -> str:
    lines = [
        "# Multi-dataset Self-training Runbook",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Scope: {report['execution_scope']}",
        f"- Overall status: `{report['overall_status']}`",
        "",
        "## Run Sequence",
        "",
        "1. Run `audit-wesad` and verify safety artifacts.",
        "2. Run `g3-2-multi-dataset-strategy`.",
        "3. Run `g3-2-multi-dataset-protocol`.",
        "4. Execute phases from `self_training_phases` in order.",
        "5. Promote model only if `model_freeze_decision` guardrails pass.",
        "",
        "## Phase Plan",
        "",
    ]
    for row in report["self_training_phases"]:
        lines.append(
            f"- `{row['phase_id']}` `{row['phase_name']}` -> `{row['status']}`; "
            f"scope=`{row['dataset_scope']}`; blockers=`{row['blockers'] or 'none'}`."
        )
        lines.append(f"  objective: {row['objective']}")

    lines.extend(["", "## Metrics Contract", ""])
    for row in report["metrics_contract"]:
        lines.append(
            f"- phase=`{row['phase_name']}`, track=`{row['track']}`, metric=`{row['metric_name']}`, role=`{row['metric_role']}`."
        )
    lines.append("")
    return "\n".join(lines)


def _build_self_training_execution_md(report: dict[str, Any]) -> str:
    phase_reports = report.get("phase_reports", {})
    phase6 = phase_reports.get("phase_6", {})
    phase8 = phase_reports.get("phase_8", {})
    lines = [
        "# Multi-dataset Self-training Execution Report",
        "",
        f"- `experiment_id`: `{report['experiment_id']}`",
        f"- Scope: {report.get('execution_scope', 'n/a')}",
        f"- Overall status: `{report.get('overall_status', 'n/a')}`",
        "",
        "## Phase Summary",
        "",
    ]
    for key in sorted(phase_reports.keys()):
        item = phase_reports[key]
        lines.append(f"- `{key}` `{item.get('phase_name', '')}` -> `{item.get('status', 'n/a')}`")
    lines.extend(
        [
            "",
            "## Promotion Signal",
            "",
            f"- delta macro_f1 (real-label self-training vs supervised): `{phase6.get('delta_macro_f1', 'n/a')}`",
            f"- final decision: `{phase8.get('decision', 'n/a')}`",
            "",
        ]
    )
    return "\n".join(lines)


def _generate_plots(plots_dir: Path, rows: list[dict[str, Any]]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    for track in ("activity", "arousal_coarse"):
        grouped: dict[str, dict[str, float]] = {}
        for row in rows:
            if row["track"] != track:
                continue
            grouped.setdefault(row["dataset_id"], {})[row["variant_name"]] = float(row["value"])
        if not grouped:
            continue
        datasets = sorted(grouped.keys())
        winners = []
        values = []
        for dataset in datasets:
            variant, value = max(grouped[dataset].items(), key=lambda item: item[1])
            winners.append(f"{dataset}:{variant}")
            values.append(value)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(winners, values, color="#2B6CB0")
        ax.set_ylim(0.0, 1.0)
        ax.set_ylabel("macro_f1")
        ax.set_title(f"G3.2 best variant per dataset ({track})")
        ax.tick_params(axis="x", rotation=20)
        fig.tight_layout()
        fig.savefig(plots_dir / f"g3-2-best-by-dataset-{track}.png", dpi=160)
        plt.close(fig)
