#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
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


DATASETS: tuple[tuple[str, str], ...] = (
    ("wesad", "wesad-v1"),
    ("grex", "grex-v1"),
    ("emowear", "emowear-v1"),
)
CLASSIFIERS: tuple[str, ...] = ("ridge_classifier", "catboost", "xgboost")
CLASS_TO_SCORE = {"low": 2, "medium": 5, "high": 8}


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
    features: dict[str, float]


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


def _meta_features(source: dict[str, float]) -> dict[str, float]:
    values = np.asarray([float(v) for v in source.values() if np.isfinite(float(v))], dtype=float)
    if values.size == 0:
        return {}
    q10, q25, q50, q75, q90 = np.percentile(values, [10, 25, 50, 75, 90])
    abs_values = np.abs(values)
    std = float(values.std())
    if std > 0:
        centered = values - float(values.mean())
        skew = float(np.mean((centered / std) ** 3))
    else:
        skew = 0.0
    return {
        "meta_count": float(values.size),
        "meta_mean": _safe_float(float(values.mean())),
        "meta_std": _safe_float(std),
        "meta_min": _safe_float(float(values.min())),
        "meta_max": _safe_float(float(values.max())),
        "meta_range": _safe_float(float(values.max() - values.min())),
        "meta_abs_mean": _safe_float(float(abs_values.mean())),
        "meta_abs_std": _safe_float(float(abs_values.std())),
        "meta_q10": _safe_float(float(q10)),
        "meta_q25": _safe_float(float(q25)),
        "meta_q50": _safe_float(float(q50)),
        "meta_q75": _safe_float(float(q75)),
        "meta_q90": _safe_float(float(q90)),
        "meta_iqr": _safe_float(float(q75 - q25)),
        "meta_skew": _safe_float(skew),
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
    labels = _load_jsonl(dataset_root / "unified" / "segment-labels.jsonl")
    split_manifest = json.loads((dataset_root / "manifest" / "split-manifest.json").read_text(encoding="utf-8"))

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
        base = _harmonized_signal_features(
            dataset_id=dataset_id,
            row=row,
            subject_token=subject_token,
            segment_id=str(row.get("segment_id", "")),
            feature_context=feature_context,
        )
        if not base:
            continue
        meta = _meta_features(base)
        if not meta:
            continue
        score = int(row.get("valence_score", 5))
        rows.append(
            Example(
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                subject_id=subject_id,
                session_id=session_id,
                segment_id=str(row.get("segment_id", "")),
                split=split,
                valence_score=score,
                valence_coarse=_valence_coarse(score),
                features=meta,
            )
        )
    return rows


def _to_matrix(rows: list[Example], feature_names: list[str]) -> np.ndarray:
    matrix = np.zeros((len(rows), len(feature_names)), dtype=float)
    for row_index, row in enumerate(rows):
        for col_index, name in enumerate(feature_names):
            matrix[row_index, col_index] = float(row.features.get(name, 0.0))
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=1e6, neginf=-1e6)
    matrix = np.clip(matrix, -1e6, 1e6)
    return matrix


def _covariance(matrix: np.ndarray) -> np.ndarray:
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=1e6, neginf=-1e6)
    matrix = np.clip(matrix, -1e6, 1e6)
    if matrix.shape[0] < 2:
        return np.eye(matrix.shape[1], dtype=float)
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    centered = np.nan_to_num(centered, nan=0.0, posinf=1e3, neginf=-1e3)
    centered = np.clip(centered, -1e3, 1e3)
    with np.errstate(all="ignore"):
        cov = (centered.T @ centered) / float(max(matrix.shape[0] - 1, 1))
    cov = np.nan_to_num(cov, nan=0.0, posinf=1e6, neginf=-1e6)
    return cov


def _matrix_sqrt(matrix: np.ndarray, inverse: bool = False, eps: float = 1e-5) -> np.ndarray:
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=1e6, neginf=-1e6)
    matrix = np.clip(matrix, -1e6, 1e6)
    values, vectors = np.linalg.eigh(matrix + eps * np.eye(matrix.shape[0], dtype=float))
    values = np.maximum(values, eps)
    if inverse:
        scale = np.diag(1.0 / np.sqrt(values))
    else:
        scale = np.diag(np.sqrt(values))
    with np.errstate(all="ignore"):
        out = vectors @ scale @ vectors.T
    out = np.nan_to_num(out, nan=0.0, posinf=1e6, neginf=-1e6)
    out = np.clip(out, -1e6, 1e6)
    return out


def _coral_align(source_x: np.ndarray, target_ref_x: np.ndarray, target_eval_x: np.ndarray) -> np.ndarray:
    if source_x.size == 0 or target_ref_x.size == 0 or target_eval_x.size == 0:
        return target_eval_x
    source_mean = source_x.mean(axis=0, keepdims=True)
    target_mean = target_ref_x.mean(axis=0, keepdims=True)
    source_cov = _covariance(source_x)
    target_cov = _covariance(target_ref_x)
    source_sqrt = _matrix_sqrt(source_cov, inverse=False)
    target_inv_sqrt = _matrix_sqrt(target_cov, inverse=True)
    centered = np.nan_to_num(target_eval_x - target_mean, nan=0.0, posinf=1e6, neginf=-1e6)
    with np.errstate(all="ignore"):
        transformed = centered @ target_inv_sqrt @ source_sqrt
    transformed = np.nan_to_num(transformed + source_mean, nan=0.0, posinf=1e6, neginf=-1e6)
    transformed = np.clip(transformed, -1e6, 1e6)
    return transformed


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    denom = exp.sum(axis=1, keepdims=True)
    denom = np.where(denom <= 0, 1.0, denom)
    return exp / denom


def _as_logits(model: Any, x: np.ndarray, class_order: list[str]) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        probs = np.asarray(model.predict_proba(x), dtype=float)
        probs = np.clip(probs, 1e-8, 1.0)
        return np.log(probs)
    if hasattr(model, "decision_function"):
        raw = np.asarray(model.decision_function(x), dtype=float)
        if raw.ndim == 1:
            raw = np.stack([-raw, raw], axis=1)
        return raw
    pred = [str(item) for item in model.predict(x)]
    logits = np.full((len(pred), len(class_order)), -8.0, dtype=float)
    for i, label in enumerate(pred):
        if label in class_order:
            logits[i, class_order.index(label)] = 8.0
    return logits


def _fit_temperature(logits: np.ndarray, labels: list[str], class_order: list[str]) -> float:
    if logits.shape[0] == 0:
        return 1.0
    y_idx = np.asarray([class_order.index(label) for label in labels], dtype=int)
    candidates = np.linspace(0.5, 3.0, 26)
    best_t = 1.0
    best_nll = float("inf")
    for temp in candidates:
        probs = _softmax(logits / temp)
        chosen = np.clip(probs[np.arange(len(y_idx)), y_idx], 1e-10, 1.0)
        nll = float(-np.mean(np.log(chosen)))
        if nll < best_nll:
            best_nll = nll
            best_t = float(temp)
    return best_t


def _score(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    metrics = compute_classification_metrics(y_true, y_pred)
    true_scores = [CLASS_TO_SCORE[item] for item in y_true]
    pred_scores = [CLASS_TO_SCORE.get(item, 5) for item in y_pred]
    return {
        "macro_f1": float(metrics.macro_f1),
        "balanced_accuracy": float(metrics.balanced_accuracy),
        "qwk": float(compute_quadratic_weighted_kappa(true_scores, pred_scores, min_rating=1, max_rating=9)),
    }


def _score_with_gate(y_true: list[str], y_pred: list[str], conf: np.ndarray, threshold: float) -> dict[str, float]:
    keep = conf >= threshold
    if keep.sum() == 0:
        return {"macro_f1_known": 0.0, "qwk_known": 0.0, "coverage": 0.0, "unknown_rate": 1.0}
    known_true = [item for item, flag in zip(y_true, keep) if flag]
    known_pred = [item for item, flag in zip(y_pred, keep) if flag]
    metrics = _score(known_true, known_pred)
    coverage = float(keep.mean())
    return {
        "macro_f1_known": metrics["macro_f1"],
        "qwk_known": metrics["qwk"],
        "coverage": coverage,
        "unknown_rate": 1.0 - coverage,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _generate_plot(matrix_rows: list[dict[str, Any]], output_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [item for item in matrix_rows if item["mode"] in ("baseline", "coral_temp")]
    if not rows:
        return
    labels = sorted({f"{item['source_dataset']}->{item['target_dataset']}" for item in rows})
    width = 0.36
    x = np.arange(len(labels), dtype=float)
    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 1.3), 4.6))
    for idx, mode in enumerate(["baseline", "coral_temp"]):
        values: list[float] = []
        for label in labels:
            pair_rows = [r for r in rows if f"{r['source_dataset']}->{r['target_dataset']}" == label and r["mode"] == mode]
            if not pair_rows:
                values.append(np.nan)
            else:
                values.append(max(float(item["macro_f1"]) for item in pair_rows))
        offset = -width / 2 if idx == 0 else width / 2
        ax.bar(x + offset, values, width=width, label=mode)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylabel("Macro F1")
    ax.set_title("E2.6 Valence Transfer: baseline vs coral_temp")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "e2-6-transfer-baseline-vs-coral-temp.png", dpi=140)
    plt.close(fig)


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

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

    feature_names: list[str] = []
    for rows in examples_by_dataset.values():
        if rows:
            feature_names = sorted(rows[0].features.keys())
            break

    matrix_rows: list[dict[str, Any]] = []
    subject_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []

    for source_dataset in ("wesad", "grex"):
        source_rows = examples_by_dataset[source_dataset]
        source_train = [row for row in source_rows if row.split == "train"]
        source_val = [row for row in source_rows if row.split == "validation"]
        if len(source_train) < 10 or len(source_val) < 5:
            continue

        x_train = _to_matrix(source_train, feature_names)
        y_train = [row.valence_coarse for row in source_train]
        x_val = _to_matrix(source_val, feature_names)
        y_val = [row.valence_coarse for row in source_val]

        for classifier_kind in CLASSIFIERS:
            model = build_estimator_classifier(classifier_kind)
            model.fit(x_train, y_train)
            class_order = [str(item) for item in getattr(model, "classes_", sorted(set(y_train)))]

            val_logits = _as_logits(model, x_val, class_order)
            temperature = _fit_temperature(val_logits, y_val, class_order)
            val_probs = _softmax(val_logits / temperature)
            val_pred = [class_order[int(idx)] for idx in val_probs.argmax(axis=1)]
            val_conf = val_probs.max(axis=1)

            threshold_candidates = np.linspace(0.55, 0.9, 8)
            selected_threshold = 0.7
            selected_score = -1.0
            for threshold in threshold_candidates:
                gate_metrics = _score_with_gate(y_val, val_pred, val_conf, float(threshold))
                if gate_metrics["unknown_rate"] > 0.5:
                    continue
                if gate_metrics["macro_f1_known"] > selected_score:
                    selected_score = float(gate_metrics["macro_f1_known"])
                    selected_threshold = float(threshold)

            calibration_rows.append(
                {
                    "source_dataset": source_dataset,
                    "classifier_kind": classifier_kind,
                    "temperature": round(temperature, 6),
                    "selected_threshold": round(selected_threshold, 6),
                    "val_macro_f1": round(_score(y_val, val_pred)["macro_f1"], 6),
                    "val_unknown_rate_at_threshold": round(1.0 - float((val_conf >= selected_threshold).mean()), 6),
                }
            )

            for target_dataset in ("wesad", "grex", "emowear"):
                target_rows = examples_by_dataset[target_dataset]
                target_ref = [row for row in target_rows if row.split in ("train", "validation")]
                target_test = [row for row in target_rows if row.split == "test"]
                if not target_ref or not target_test:
                    continue
                x_ref = _to_matrix(target_ref, feature_names)
                x_test = _to_matrix(target_test, feature_names)
                y_test = [row.valence_coarse for row in target_test]

                baseline_pred = [str(item) for item in model.predict(x_test)]
                baseline_metrics = _score(y_test, baseline_pred)
                matrix_rows.append(
                    {
                        "source_dataset": source_dataset,
                        "target_dataset": target_dataset,
                        "classifier_kind": classifier_kind,
                        "mode": "baseline",
                        "macro_f1": round(baseline_metrics["macro_f1"], 6),
                        "balanced_accuracy": round(baseline_metrics["balanced_accuracy"], 6),
                        "qwk": round(baseline_metrics["qwk"], 6),
                        "support": len(y_test),
                    }
                )

                x_test_coral = _coral_align(source_x=x_train, target_ref_x=x_ref, target_eval_x=x_test)
                coral_pred = [str(item) for item in model.predict(x_test_coral)]
                coral_metrics = _score(y_test, coral_pred)
                matrix_rows.append(
                    {
                        "source_dataset": source_dataset,
                        "target_dataset": target_dataset,
                        "classifier_kind": classifier_kind,
                        "mode": "coral",
                        "macro_f1": round(coral_metrics["macro_f1"], 6),
                        "balanced_accuracy": round(coral_metrics["balanced_accuracy"], 6),
                        "qwk": round(coral_metrics["qwk"], 6),
                        "support": len(y_test),
                    }
                )

                logits = _as_logits(model, x_test_coral, class_order)
                probs = _softmax(logits / temperature)
                pred = [class_order[int(idx)] for idx in probs.argmax(axis=1)]
                conf = probs.max(axis=1)
                temp_metrics = _score(y_test, pred)
                gated = _score_with_gate(y_test, pred, conf, selected_threshold)
                matrix_rows.append(
                    {
                        "source_dataset": source_dataset,
                        "target_dataset": target_dataset,
                        "classifier_kind": classifier_kind,
                        "mode": "coral_temp",
                        "macro_f1": round(temp_metrics["macro_f1"], 6),
                        "balanced_accuracy": round(temp_metrics["balanced_accuracy"], 6),
                        "qwk": round(temp_metrics["qwk"], 6),
                        "support": len(y_test),
                    }
                )
                matrix_rows.append(
                    {
                        "source_dataset": source_dataset,
                        "target_dataset": target_dataset,
                        "classifier_kind": classifier_kind,
                        "mode": "coral_temp_gate",
                        "macro_f1": round(gated["macro_f1_known"], 6),
                        "balanced_accuracy": round(gated["coverage"], 6),
                        "qwk": round(gated["qwk_known"], 6),
                        "support": int((conf >= selected_threshold).sum()),
                    }
                )

                by_subject_true: dict[str, list[str]] = defaultdict(list)
                by_subject_pred: dict[str, list[str]] = defaultdict(list)
                for row, p in zip(target_test, pred):
                    by_subject_true[row.subject_id].append(row.valence_coarse)
                    by_subject_pred[row.subject_id].append(p)
                for subject_id in sorted(by_subject_true):
                    sm = _score(by_subject_true[subject_id], by_subject_pred[subject_id])
                    subject_rows.append(
                        {
                            "source_dataset": source_dataset,
                            "target_dataset": target_dataset,
                            "classifier_kind": classifier_kind,
                            "mode": "coral_temp",
                            "subject_id": subject_id,
                            "macro_f1": round(sm["macro_f1"], 6),
                            "qwk": round(sm["qwk"], 6),
                            "support": len(by_subject_true[subject_id]),
                        }
                    )

    _write_csv(output_dir / "adaptation-matrix.csv", matrix_rows)
    _write_csv(output_dir / "calibration-summary.csv", calibration_rows)
    _write_csv(output_dir / "adaptation-subject-metrics.csv", subject_rows)
    _generate_plot(matrix_rows, output_dir / "plots")

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in matrix_rows:
        grouped[(str(row["source_dataset"]), str(row["target_dataset"]), str(row["classifier_kind"]))].append(row)
    summary_rows: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        baseline = next((r for r in rows if r["mode"] == "baseline"), None)
        best = max(rows, key=lambda r: float(r["macro_f1"]))
        if baseline is None:
            continue
        summary_rows.append(
            {
                "source_dataset": key[0],
                "target_dataset": key[1],
                "classifier_kind": key[2],
                "baseline_macro_f1": baseline["macro_f1"],
                "best_mode": best["mode"],
                "best_macro_f1": best["macro_f1"],
                "delta_macro_f1": round(float(best["macro_f1"]) - float(baseline["macro_f1"]), 6),
            }
        )
    _write_csv(output_dir / "adaptation-summary.csv", summary_rows)

    report = {
        "experiment_id": f"e2-6-valence-domain-adaptation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Domain adaptation (CORAL) + calibration (temperature scaling) + confidence gating",
        "sources": ["wesad", "grex"],
        "targets": ["wesad", "grex", "emowear"],
        "classifiers": list(CLASSIFIERS),
        "summary": summary_rows,
    }
    (output_dir / "e2-6-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# E2.6 Domain Adaptation Report",
        "",
        "## Summary",
        "",
    ]
    for row in summary_rows:
        lines.append(
            f"- `{row['source_dataset']}->{row['target_dataset']}` `{row['classifier_kind']}`: "
            f"`baseline={float(row['baseline_macro_f1']):.6f}`, "
            f"`best={row['best_mode']} ({float(row['best_macro_f1']):.6f})`, "
            f"`delta={float(row['delta_macro_f1']):+.6f}`"
        )
    (output_dir / "research-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.6 valence domain adaptation + calibration")
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation"),
    )
    parser.add_argument("--min-confidence", type=float, default=0.7)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
