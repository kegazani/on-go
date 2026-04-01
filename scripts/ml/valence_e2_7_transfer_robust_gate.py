#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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
    split: str
    subject_id: str
    valence_coarse: str
    features: dict[str, float]


def _valence_coarse(score: int) -> str:
    if score <= 3:
        return "low"
    if score <= 6:
        return "medium"
    return "high"


def _meta_features(source: dict[str, float]) -> dict[str, float]:
    values = np.asarray([float(v) for v in source.values() if np.isfinite(float(v))], dtype=float)
    if values.size == 0:
        return {}
    q25, q50, q75 = np.percentile(values, [25, 50, 75])
    return {
        "meta_count": float(values.size),
        "meta_mean": float(values.mean()),
        "meta_std": float(values.std()),
        "meta_min": float(values.min()),
        "meta_max": float(values.max()),
        "meta_range": float(values.max() - values.min()),
        "meta_q25": float(q25),
        "meta_q50": float(q50),
        "meta_q75": float(q75),
        "meta_iqr": float(q75 - q25),
        "meta_abs_mean": float(np.abs(values).mean()),
        "meta_abs_std": float(np.abs(values).std()),
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
    root = artifacts_root / dataset_id / "artifacts" / dataset_id / dataset_version
    labels = _load_jsonl(root / "unified" / "segment-labels.jsonl")
    split_manifest = json.loads((root / "manifest" / "split-manifest.json").read_text(encoding="utf-8"))

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
        token = _subject_token_from_session_id(session_id)
        if token is None:
            continue
        subject_id = f"{dataset_id}:{token}"
        split = split_index.get(subject_id)
        if split is None:
            continue
        raw = _harmonized_signal_features(
            dataset_id=dataset_id,
            row=row,
            subject_token=token,
            segment_id=str(row.get("segment_id", "")),
            feature_context=feature_context,
        )
        if not raw:
            continue
        meta = _meta_features(raw)
        if not meta:
            continue
        rows.append(
            Example(
                dataset_id=dataset_id,
                split=split,
                subject_id=subject_id,
                valence_coarse=_valence_coarse(int(row.get("valence_score", 5))),
                features=meta,
            )
        )
    return rows


def _to_matrix(rows: list[Example], feature_names: list[str]) -> np.ndarray:
    matrix = np.zeros((len(rows), len(feature_names)), dtype=float)
    for i, row in enumerate(rows):
        for j, name in enumerate(feature_names):
            matrix[i, j] = float(row.features.get(name, 0.0))
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=1e6, neginf=-1e6)
    matrix = np.clip(matrix, -1e6, 1e6)
    return matrix


def _score(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    cls = compute_classification_metrics(y_true, y_pred)
    yt = [CLASS_TO_SCORE[item] for item in y_true]
    yp = [CLASS_TO_SCORE.get(item, 5) for item in y_pred]
    return {
        "macro_f1": float(cls.macro_f1),
        "balanced_accuracy": float(cls.balanced_accuracy),
        "qwk": float(compute_quadratic_weighted_kappa(yt, yp, min_rating=1, max_rating=9)),
    }


def _feature_shift_score(source_x: np.ndarray, target_x: np.ndarray) -> np.ndarray:
    s_mean = source_x.mean(axis=0)
    t_mean = target_x.mean(axis=0)
    s_std = source_x.std(axis=0)
    t_std = target_x.std(axis=0)
    pooled = np.sqrt((s_std**2 + t_std**2) / 2.0)
    pooled = np.where(pooled <= 1e-6, 1e-6, pooled)
    mean_diff = np.abs(s_mean - t_mean) / pooled
    var_ratio = np.maximum(s_std / np.where(t_std <= 1e-6, 1e-6, t_std), t_std / np.where(s_std <= 1e-6, 1e-6, s_std))
    score = mean_diff + np.maximum(0.0, var_ratio - 1.0)
    return np.nan_to_num(score, nan=1e6, posinf=1e6, neginf=1e6)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


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

    feature_names = sorted(next(iter(examples_by_dataset.values()))[0].features.keys())

    comparison_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []

    for source_dataset in ("wesad", "grex"):
        source = examples_by_dataset[source_dataset]
        source_train = [r for r in source if r.split == "train"]
        source_y = [r.valence_coarse for r in source_train]
        x_source = _to_matrix(source_train, feature_names)

        for target_dataset in ("wesad", "grex", "emowear"):
            target = examples_by_dataset[target_dataset]
            target_ref = [r for r in target if r.split in ("train", "validation")]
            target_test = [r for r in target if r.split == "test"]
            if not target_ref or not target_test:
                continue
            x_ref = _to_matrix(target_ref, feature_names)
            x_test = _to_matrix(target_test, feature_names)
            y_test = [r.valence_coarse for r in target_test]

            shift = _feature_shift_score(x_source, x_ref)
            keep = shift <= args.shift_threshold
            if int(keep.sum()) < 4:
                keep = np.argsort(shift)[: min(6, len(shift))]
                mask = np.zeros(len(shift), dtype=bool)
                mask[keep] = True
                keep = mask
            selected = [name for idx, name in enumerate(feature_names) if bool(keep[idx])]

            x_source_sel = x_source[:, keep]
            x_test_sel = x_test[:, keep]
            feature_rows.append(
                {
                    "source_dataset": source_dataset,
                    "target_dataset": target_dataset,
                    "selected_feature_count": int(len(selected)),
                    "selected_features": "|".join(selected),
                    "shift_threshold": float(args.shift_threshold),
                    "mean_shift_selected": float(shift[keep].mean()) if int(keep.sum()) else 0.0,
                }
            )

            for kind in CLASSIFIERS:
                model = build_estimator_classifier(kind)
                model.fit(x_source_sel, source_y)
                pred = [str(item) for item in model.predict(x_test_sel)]
                metrics = _score(y_test, pred)
                comparison_rows.append(
                    {
                        "source_dataset": source_dataset,
                        "target_dataset": target_dataset,
                        "classifier_kind": kind,
                        "macro_f1": round(metrics["macro_f1"], 6),
                        "balanced_accuracy": round(metrics["balanced_accuracy"], 6),
                        "qwk": round(metrics["qwk"], 6),
                        "support": len(y_test),
                    }
                )

    trusted_rows: list[dict[str, Any]] = []
    for kind in CLASSIFIERS:
        wg = next((r for r in comparison_rows if r["source_dataset"] == "wesad" and r["target_dataset"] == "grex" and r["classifier_kind"] == kind), None)
        gw = next((r for r in comparison_rows if r["source_dataset"] == "grex" and r["target_dataset"] == "wesad" and r["classifier_kind"] == kind), None)
        if wg is None or gw is None:
            continue
        min_cross = min(float(wg["macro_f1"]), float(gw["macro_f1"]))
        trusted_rows.append(
            {
                "classifier_kind": kind,
                "wesad_to_grex_macro_f1": wg["macro_f1"],
                "grex_to_wesad_macro_f1": gw["macro_f1"],
                "min_cross_macro_f1": round(min_cross, 6),
                "is_trusted": bool(min_cross >= args.trusted_floor),
            }
        )

    _write_csv(output_dir / "model-comparison.csv", comparison_rows)
    _write_csv(output_dir / "feature-shift-selection.csv", feature_rows)
    _write_csv(output_dir / "trusted-models.csv", trusted_rows)

    trusted_models = [r["classifier_kind"] for r in trusted_rows if bool(r["is_trusted"])]
    decision = "revisit_limited_production" if trusted_models else "keep_exploratory"
    report = {
        "experiment_id": f"e2-7-valence-transfer-robust-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "trusted_floor": args.trusted_floor,
        "trusted_models": trusted_models,
        "summary": trusted_rows,
    }
    (output_dir / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# E2.7 Transfer-robust Re-gate",
        "",
        f"- Decision: `{decision}`",
        f"- Trusted floor: `{args.trusted_floor}`",
    ]
    for row in trusted_rows:
        lines.append(
            f"- `{row['classifier_kind']}`: `wesad->grex={float(row['wesad_to_grex_macro_f1']):.6f}`, "
            f"`grex->wesad={float(row['grex_to_wesad_macro_f1']):.6f}`, "
            f"`min={float(row['min_cross_macro_f1']):.6f}`, trusted=`{row['is_trusted']}`"
        )
    (output_dir / "research-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.7 transfer-robust valence re-gate")
    parser.add_argument("--artifacts-root", type=Path, default=Path("/Users/kgz/Desktop/p/on-go/data/external"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-7-valence-transfer-robust-regate"),
    )
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--shift-threshold", type=float, default=1.2)
    parser.add_argument("--trusted-floor", type=float, default=0.40)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
