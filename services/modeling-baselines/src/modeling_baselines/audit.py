from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from modeling_baselines.estimators import build_estimator_classifier
from modeling_baselines.metrics import compute_classification_metrics
from modeling_baselines.pipeline import (
    PROTOCOL_SHORTCUT_FEATURE_NAMES,
    PipelinePaths,
    SegmentExample,
    _load_examples,
    _select_feature_names,
)

FORBIDDEN_FEATURE_PREFIXES = ("label_",)
SINGLE_FEATURE_ALERT_THRESHOLD = 0.95


def run_wesad_safety_audit(
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

    all_feature_names = sorted(examples[0].features.keys())
    selected_feature_rows = _selected_feature_rows(all_feature_names)
    selected_feature_names = sorted({str(row["feature_name"]) for row in selected_feature_rows})
    forbidden_selected = sorted(
        {
            feature_name
            for feature_name in selected_feature_names
            if _is_forbidden_feature_name(feature_name)
        }
    )

    split_audit = _build_split_audit(examples=examples, split_manifest=split_manifest)
    leakage_audit = _build_leakage_audit(
        examples=examples,
        selected_feature_names=selected_feature_names,
        forbidden_selected=forbidden_selected,
    )

    experiment_id = f"audit-wesad-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    report = {
        "experiment_id": experiment_id,
        "run_kind": "audit-wesad",
        "dataset_version": f"{dataset_id}:{dataset_version}",
        "label_set_version": "a2-v1",
        "preprocessing_version": preprocessing_version,
        "split_manifest_version": f"{dataset_id}:{dataset_version}:{split_manifest.get('strategy', 'subject-wise')}",
        "min_confidence": min_confidence,
        "status": "failed" if _has_blocking_findings(split_audit, leakage_audit) else "passed",
        "blocking_findings": _blocking_findings(split_audit, leakage_audit),
        "summary_metrics": {
            "features_total": len(all_feature_names),
            "selected_features_total": len(selected_feature_names),
            "forbidden_selected_features": len(forbidden_selected),
            "duplicate_segment_ids": split_audit["duplicate_segment_ids"],
            "split_overlap_subject_ids": len(split_audit["subject_overlap_pairs"]),
            "top_single_feature_activity_macro_f1": leakage_audit["single_feature_probe"]["activity"]["top_macro_f1"],
            "top_single_feature_arousal_macro_f1": leakage_audit["single_feature_probe"]["arousal_coarse"]["top_macro_f1"],
            "top_single_feature_valence_macro_f1": leakage_audit["single_feature_probe"]["valence_coarse"]["top_macro_f1"],
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    output_root = paths.output_dir / dataset_id / dataset_version / "safety-audit"
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / "evaluation-report.json"
    selected_features_path = output_root / "selected-features.csv"
    split_audit_path = output_root / "split-audit.json"
    leakage_audit_path = output_root / "leakage-audit.json"

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(selected_features_path, selected_feature_rows)
    split_audit_path.write_text(json.dumps(split_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    leakage_audit_path.write_text(json.dumps(leakage_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "experiment_id": experiment_id,
        "report_path": str(report_path),
        "selected_features_path": str(selected_features_path),
        "split_audit_path": str(split_audit_path),
        "leakage_audit_path": str(leakage_audit_path),
        "status": report["status"],
    }


def _selected_feature_rows(all_feature_names: list[str]) -> list[dict[str, Any]]:
    profiles = {
        "watch_only": ("watch_",),
        "chest_only": ("chest_",),
        "fusion": ("watch_", "chest_"),
    }

    rows: list[dict[str, Any]] = []
    for profile_name, prefixes in profiles.items():
        selected = _select_feature_names(all_feature_names, prefixes)
        for feature_name in selected:
            rows.append(
                {
                    "profile": profile_name,
                    "feature_name": feature_name,
                    "forbidden": _is_forbidden_feature_name(feature_name),
                }
            )
    return rows


def _build_split_audit(examples: list[SegmentExample], split_manifest: dict[str, Any]) -> dict[str, Any]:
    overlaps = _subject_overlap_pairs(split_manifest)
    duplicate_segment_ids = len(examples) - len({item.segment_id for item in examples})

    split_payload: dict[str, Any] = {}
    for split_name in ("train", "validation", "test"):
        rows = [item for item in examples if item.split == split_name]
        split_payload[split_name] = {
            "subjects": len({item.subject_id for item in rows}),
            "sessions": len({item.session_id for item in rows}),
            "segments": len(rows),
            "activity_labels": _coverage_counts(rows, "activity_label"),
            "arousal_coarse_labels": _coverage_counts(rows, "arousal_coarse"),
            "valence_coarse_labels": _coverage_counts(rows, "valence_coarse"),
        }

    return {
        "split_strategy": split_manifest.get("strategy", "unknown"),
        "subject_overlap_pairs": overlaps,
        "duplicate_segment_ids": duplicate_segment_ids,
        "splits": split_payload,
    }


def _build_leakage_audit(
    examples: list[SegmentExample],
    selected_feature_names: list[str],
    forbidden_selected: list[str],
) -> dict[str, Any]:
    activity_probe = _single_feature_probe(examples, selected_feature_names, "activity_label")
    arousal_probe = _single_feature_probe(examples, selected_feature_names, "arousal_coarse")
    valence_probe = _single_feature_probe(examples, selected_feature_names, "valence_coarse")

    return {
        "forbidden_selected_features": forbidden_selected,
        "single_feature_probe": {
            "activity": activity_probe,
            "arousal_coarse": arousal_probe,
            "valence_coarse": valence_probe,
        },
        "alerts": {
            "activity_single_feature_shortcut": activity_probe["top_macro_f1"] >= SINGLE_FEATURE_ALERT_THRESHOLD,
            "arousal_single_feature_shortcut": arousal_probe["top_macro_f1"] >= SINGLE_FEATURE_ALERT_THRESHOLD,
            "valence_single_feature_shortcut": valence_probe["top_macro_f1"] >= SINGLE_FEATURE_ALERT_THRESHOLD,
        },
    }


def _single_feature_probe(
    examples: list[SegmentExample],
    feature_names: list[str],
    target_field: str,
) -> dict[str, Any]:
    train = [item for item in examples if item.split == "train"]
    test = [item for item in examples if item.split == "test"]

    results: list[dict[str, Any]] = []
    for feature_name in feature_names:
        x_train = np.asarray([[float(item.features.get(feature_name, 0.0))] for item in train], dtype=float)
        x_test = np.asarray([[float(item.features.get(feature_name, 0.0))] for item in test], dtype=float)
        y_train = [str(getattr(item, target_field)) for item in train]
        y_test = [str(getattr(item, target_field)) for item in test]

        if len(set(y_train)) < 2 or len(set(y_test)) < 2:
            continue

        model = build_estimator_classifier("decision_tree")
        try:
            model.fit(x_train, y_train)
            predicted = model.predict(x_test)
            macro_f1 = compute_classification_metrics(y_test, predicted).macro_f1
        except Exception:
            continue

        results.append({"feature_name": feature_name, "macro_f1": macro_f1})

    results.sort(key=lambda item: float(item["macro_f1"]), reverse=True)
    return {
        "top_macro_f1": float(results[0]["macro_f1"]) if results else 0.0,
        "top_features": results[:10],
        "probed_feature_count": len(results),
    }


def _subject_overlap_pairs(split_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    split_names = ("train_subject_ids", "validation_subject_ids", "test_subject_ids")
    mapped = {name: set(str(item) for item in split_manifest.get(name, [])) for name in split_names}
    pairs = [
        ("train_subject_ids", "validation_subject_ids"),
        ("train_subject_ids", "test_subject_ids"),
        ("validation_subject_ids", "test_subject_ids"),
    ]
    rows = []
    for left, right in pairs:
        overlap = sorted(mapped[left].intersection(mapped[right]))
        if overlap:
            rows.append({"left": left, "right": right, "overlap_subject_ids": overlap})
    return rows


def _coverage_counts(examples: list[SegmentExample], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in examples:
        key = str(getattr(item, field_name))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _is_forbidden_feature_name(feature_name: str) -> bool:
    if feature_name in PROTOCOL_SHORTCUT_FEATURE_NAMES:
        return True
    return any(feature_name.startswith(prefix) for prefix in FORBIDDEN_FEATURE_PREFIXES)


def _has_blocking_findings(split_audit: dict[str, Any], leakage_audit: dict[str, Any]) -> bool:
    if split_audit["subject_overlap_pairs"]:
        return True
    if split_audit["duplicate_segment_ids"] > 0:
        return True
    if leakage_audit["forbidden_selected_features"]:
        return True
    return bool(
        leakage_audit["alerts"]["activity_single_feature_shortcut"]
        or leakage_audit["alerts"]["arousal_single_feature_shortcut"]
        or leakage_audit["alerts"]["valence_single_feature_shortcut"]
    )


def _blocking_findings(split_audit: dict[str, Any], leakage_audit: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if split_audit["subject_overlap_pairs"]:
        findings.append("split_subject_overlap")
    if split_audit["duplicate_segment_ids"] > 0:
        findings.append("duplicate_segment_ids")
    if leakage_audit["forbidden_selected_features"]:
        findings.append("forbidden_selected_features")
    if leakage_audit["alerts"]["activity_single_feature_shortcut"]:
        findings.append("activity_single_feature_shortcut")
    if leakage_audit["alerts"]["arousal_single_feature_shortcut"]:
        findings.append("arousal_single_feature_shortcut")
    if leakage_audit["alerts"]["valence_single_feature_shortcut"]:
        findings.append("valence_single_feature_shortcut")
    return findings


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
