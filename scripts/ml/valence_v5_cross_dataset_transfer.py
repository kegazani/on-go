#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from modeling_baselines.estimators import build_estimator_classifier
from modeling_baselines.metrics import compute_classification_metrics, compute_quadratic_weighted_kappa
from modeling_baselines.multi_dataset import (
    _harmonized_signal_features,
    _new_signal_feature_context,
    _subject_token_from_session_id,
)
from modeling_baselines.pipeline import CentroidClassifier


DATASETS: tuple[tuple[str, str], ...] = (
    ("wesad", "wesad-v1"),
    ("grex", "grex-v1"),
    ("emowear", "emowear-v1"),
)

CLASSIFIERS: tuple[str, ...] = ("centroid", "ridge_classifier", "catboost", "xgboost")
VALENCE_CLASS_TO_SCORE = {"low": 2, "medium": 5, "high": 8}


@dataclass(frozen=True)
class Example:
    dataset_id: str
    dataset_version: str
    subject_id: str
    session_id: str
    segment_id: str
    split: str
    valence_score: int
    valence_coarse: str
    meta_features: dict[str, float]


def _valence_coarse(score: int) -> str:
    if score <= 3:
        return "low"
    if score <= 6:
        return "medium"
    return "high"


def _safe_float(value: float, default: float = 0.0) -> float:
    if np.isfinite(value):
        return float(value)
    return default


def _meta_features(features: dict[str, float]) -> dict[str, float]:
    values = np.asarray([float(v) for v in features.values() if np.isfinite(float(v))], dtype=float)
    if values.size == 0:
        return {}
    abs_values = np.abs(values)
    q10, q25, q50, q75, q90 = np.percentile(values, [10, 25, 50, 75, 90])
    neg = float((values < 0).sum()) / float(values.size)
    pos = float((values > 0).sum()) / float(values.size)
    std = float(values.std())
    if std > 0:
        centered = values - float(values.mean())
        skew = float(np.mean((centered / std) ** 3))
        kurt = float(np.mean((centered / std) ** 4))
    else:
        skew = 0.0
        kurt = 0.0
    return {
        "meta_count": float(values.size),
        "meta_mean": _safe_float(float(values.mean())),
        "meta_std": _safe_float(std),
        "meta_min": _safe_float(float(values.min())),
        "meta_max": _safe_float(float(values.max())),
        "meta_range": _safe_float(float(values.max() - values.min())),
        "meta_abs_mean": _safe_float(float(abs_values.mean())),
        "meta_abs_std": _safe_float(float(abs_values.std())),
        "meta_l2": _safe_float(float(np.sqrt(np.sum(values**2)))),
        "meta_q10": _safe_float(float(q10)),
        "meta_q25": _safe_float(float(q25)),
        "meta_q50": _safe_float(float(q50)),
        "meta_q75": _safe_float(float(q75)),
        "meta_q90": _safe_float(float(q90)),
        "meta_iqr": _safe_float(float(q75 - q25)),
        "meta_pos_ratio": _safe_float(pos),
        "meta_neg_ratio": _safe_float(neg),
        "meta_skew": _safe_float(skew),
        "meta_kurtosis": _safe_float(kurt),
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_examples(
    artifacts_root: Path,
    dataset_id: str,
    dataset_version: str,
    min_confidence: float,
    feature_context: Any,
) -> list[Example]:
    dataset_root = artifacts_root / dataset_id / "artifacts" / dataset_id / dataset_version
    labels_path = dataset_root / "unified" / "segment-labels.jsonl"
    split_path = dataset_root / "manifest" / "split-manifest.json"
    labels = _load_jsonl(labels_path)
    split_manifest = json.loads(split_path.read_text(encoding="utf-8"))

    split_index: dict[str, str] = {}
    for token in split_manifest.get("train_subject_ids", []):
        split_index[str(token)] = "train"
    for token in split_manifest.get("validation_subject_ids", []):
        split_index[str(token)] = "validation"
    for token in split_manifest.get("test_subject_ids", []):
        split_index[str(token)] = "test"

    rows: list[Example] = []
    for row in labels:
        if float(row.get("confidence", 0.0)) < min_confidence:
            continue
        session_id = str(row.get("session_id", ""))
        subject_token = _subject_token_from_session_id(session_id)
        if subject_token is None:
            continue
        subject_id = f"{dataset_id}:{subject_token}"
        split = split_index.get(subject_id)
        if split is None:
            continue
        valence_score = int(row.get("valence_score", 5))
        base_features = _harmonized_signal_features(
            dataset_id=dataset_id,
            row=row,
            subject_token=subject_token,
            segment_id=str(row.get("segment_id", "")),
            feature_context=feature_context,
        )
        if not base_features:
            continue
        features = _meta_features(base_features)
        if not features:
            continue
        rows.append(
            Example(
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                subject_id=subject_id,
                session_id=session_id,
                segment_id=str(row.get("segment_id", "")),
                split=split,
                valence_score=valence_score,
                valence_coarse=_valence_coarse(valence_score),
                meta_features=features,
            )
        )
    return rows


def _build_classifier(kind: str) -> Any:
    if kind == "centroid":
        return CentroidClassifier()
    return build_estimator_classifier(kind)


def _to_matrix(rows: list[Example], feature_names: list[str]) -> np.ndarray:
    matrix = np.zeros((len(rows), len(feature_names)), dtype=float)
    for row_index, row in enumerate(rows):
        for col_index, name in enumerate(feature_names):
            matrix[row_index, col_index] = float(row.meta_features.get(name, 0.0))
    return matrix


def _score_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    cls = compute_classification_metrics(y_true, y_pred)
    y_true_score = [VALENCE_CLASS_TO_SCORE[item] for item in y_true]
    y_pred_score = [VALENCE_CLASS_TO_SCORE.get(item, 5) for item in y_pred]
    return {
        "macro_f1": float(cls.macro_f1),
        "balanced_accuracy": float(cls.balanced_accuracy),
        "qwk": float(compute_quadratic_weighted_kappa(y_true_score, y_pred_score, min_rating=1, max_rating=9)),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _generate_plots(matrix_rows: list[dict[str, Any]], output_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    for metric in ("macro_f1", "qwk"):
        rows = [item for item in matrix_rows if item["split"] == "test"]
        if not rows:
            continue
        axis_models = sorted({str(item["classifier_kind"]) for item in rows})
        axis_pairs = sorted({f"{item['source_dataset']}->{item['target_dataset']}" for item in rows})
        data = np.full((len(axis_models), len(axis_pairs)), np.nan, dtype=float)
        for item in rows:
            row_index = axis_models.index(str(item["classifier_kind"]))
            col_index = axis_pairs.index(f"{item['source_dataset']}->{item['target_dataset']}")
            data[row_index, col_index] = float(item[metric])
        fig, ax = plt.subplots(figsize=(max(9, len(axis_pairs) * 1.15), 3.6 + len(axis_models) * 0.4))
        im = ax.imshow(data, cmap="viridis", aspect="auto", vmin=0.0, vmax=1.0)
        ax.set_xticks(np.arange(len(axis_pairs)))
        ax.set_xticklabels(axis_pairs, rotation=40, ha="right")
        ax.set_yticks(np.arange(len(axis_models)))
        ax.set_yticklabels(axis_models)
        ax.set_title(f"V5 Cross-dataset Valence {metric.upper()} (test)")
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                value = data[i, j]
                if np.isnan(value):
                    continue
                ax.text(j, i, f"{value:.3f}", ha="center", va="center", color="white", fontsize=8)
        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        fig.savefig(output_dir / f"v5-transfer-{metric}.png", dpi=140)
        plt.close(fig)


def run(args: argparse.Namespace) -> dict[str, Any]:
    feature_context = _new_signal_feature_context(args.artifacts_root)
    examples_by_dataset: dict[str, list[Example]] = {}
    for dataset_id, dataset_version in DATASETS:
        examples_by_dataset[dataset_id] = _load_examples(
            artifacts_root=args.artifacts_root,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            min_confidence=args.min_confidence,
            feature_context=feature_context,
        )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix_rows: list[dict[str, Any]] = []
    subject_rows: list[dict[str, Any]] = []
    failed_rows: list[dict[str, Any]] = []

    feature_names: list[str] = []
    for rows in examples_by_dataset.values():
        if rows:
            feature_names = sorted(rows[0].meta_features.keys())
            break

    for source_dataset in ("wesad", "grex"):
        source_rows = examples_by_dataset.get(source_dataset, [])
        source_train = [row for row in source_rows if row.split in ("train", "validation")]
        if len({row.valence_coarse for row in source_train}) < 2:
            continue
        x_train = _to_matrix(source_train, feature_names)
        y_train = [row.valence_coarse for row in source_train]

        for classifier_kind in CLASSIFIERS:
            try:
                model = _build_classifier(classifier_kind)
                model.fit(x_train, y_train)
            except Exception as exc:
                failed_rows.append(
                    {
                        "source_dataset": source_dataset,
                        "classifier_kind": classifier_kind,
                        "stage": "fit",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                continue

            for target_dataset in ("wesad", "grex", "emowear"):
                target_rows = [row for row in examples_by_dataset.get(target_dataset, []) if row.split == "test"]
                if not target_rows:
                    continue
                y_true = [row.valence_coarse for row in target_rows]
                x_test = _to_matrix(target_rows, feature_names)
                try:
                    y_pred = [str(item) for item in model.predict(x_test)]
                    metrics = _score_metrics(y_true, y_pred)
                except Exception as exc:
                    failed_rows.append(
                        {
                            "source_dataset": source_dataset,
                            "target_dataset": target_dataset,
                            "classifier_kind": classifier_kind,
                            "stage": "predict",
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        }
                    )
                    continue

                split_tag = "in_domain_test" if source_dataset == target_dataset else "cross_dataset_test"
                matrix_rows.append(
                    {
                        "source_dataset": source_dataset,
                        "target_dataset": target_dataset,
                        "classifier_kind": classifier_kind,
                        "split": "test",
                        "evaluation_type": split_tag,
                        "macro_f1": round(metrics["macro_f1"], 6),
                        "balanced_accuracy": round(metrics["balanced_accuracy"], 6),
                        "qwk": round(metrics["qwk"], 6),
                        "support": len(target_rows),
                        "true_classes": "|".join(sorted(set(y_true))),
                    }
                )

                by_subject_true: dict[str, list[str]] = defaultdict(list)
                by_subject_pred: dict[str, list[str]] = defaultdict(list)
                for row, pred in zip(target_rows, y_pred):
                    by_subject_true[row.subject_id].append(row.valence_coarse)
                    by_subject_pred[row.subject_id].append(pred)
                for subject_id in sorted(by_subject_true):
                    sub_metrics = _score_metrics(by_subject_true[subject_id], by_subject_pred[subject_id])
                    subject_rows.append(
                        {
                            "source_dataset": source_dataset,
                            "target_dataset": target_dataset,
                            "classifier_kind": classifier_kind,
                            "subject_id": subject_id,
                            "macro_f1": round(sub_metrics["macro_f1"], 6),
                            "qwk": round(sub_metrics["qwk"], 6),
                            "support": len(by_subject_true[subject_id]),
                        }
                    )

    summary_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in matrix_rows:
        grouped[(str(row["source_dataset"]), str(row["target_dataset"]))].append(row)
    for key, rows in sorted(grouped.items()):
        winner = max(rows, key=lambda item: (float(item["macro_f1"]), float(item["qwk"])))
        summary_rows.append(
            {
                "source_dataset": key[0],
                "target_dataset": key[1],
                "winner_classifier_kind": winner["classifier_kind"],
                "winner_macro_f1": winner["macro_f1"],
                "winner_qwk": winner["qwk"],
                "candidates_tested": len(rows),
            }
        )

    coverage_rows: list[dict[str, Any]] = []
    for dataset_id in ("wesad", "grex", "emowear"):
        rows = examples_by_dataset.get(dataset_id, [])
        split_counts = Counter(row.split for row in rows)
        class_counts = Counter(row.valence_coarse for row in rows)
        coverage_rows.append(
            {
                "dataset_id": dataset_id,
                "rows_total": len(rows),
                "rows_train": split_counts.get("train", 0),
                "rows_validation": split_counts.get("validation", 0),
                "rows_test": split_counts.get("test", 0),
                "class_low": class_counts.get("low", 0),
                "class_medium": class_counts.get("medium", 0),
                "class_high": class_counts.get("high", 0),
            }
        )

    _write_csv(output_dir / "transfer-matrix.csv", matrix_rows)
    _write_csv(output_dir / "transfer-summary.csv", summary_rows)
    _write_csv(output_dir / "transfer-subject-metrics.csv", subject_rows)
    _write_csv(output_dir / "transfer-data-coverage.csv", coverage_rows)
    _write_csv(output_dir / "transfer-failed.csv", failed_rows)
    _generate_plots(matrix_rows=matrix_rows, output_dir=output_dir / "plots")

    report = {
        "experiment_id": f"e2-5-valence-v5-cross-dataset-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Cross-dataset transfer validation for valence using harmonized meta-features; no new dataset creation.",
        "sources": ["wesad", "grex"],
        "targets": ["wesad", "grex", "emowear"],
        "classifiers": list(CLASSIFIERS),
        "winners": summary_rows,
        "known_limits": [
            "Transfer uses harmonized distributional meta-features for cross-dataset comparability.",
            "EmoWear labels are proxy-tier and do not include high valence class in this split.",
            "This step validates transfer stability, not production promotion alone.",
        ],
    }
    (output_dir / "v5-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# E2.5.V5 Transfer Report",
        "",
        "## Goal",
        "",
        "Validate that valence gains are not only a WESAD split artifact by checking transfer across datasets.",
        "",
        "## Winners",
        "",
    ]
    for row in summary_rows:
        lines.append(
            f"- `{row['source_dataset']} -> {row['target_dataset']}`: `{row['winner_classifier_kind']}` "
            f"(macro_f1={float(row['winner_macro_f1']):.6f}, qwk={float(row['winner_qwk']):.6f})"
        )
    if failed_rows:
        lines.extend(["", "## Failed runs", ""])
        lines.append(f"- Failed cases: `{len(failed_rows)}` (see `transfer-failed.csv`).")
    (output_dir / "v5-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.5.V5 valence cross-dataset transfer validation")
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external"),
        help="Root path with dataset artifacts (contains wesad/grex/emowear).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v5-cross-dataset-transfer"
        ),
        help="Output directory for V5 artifacts.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold for labels.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
