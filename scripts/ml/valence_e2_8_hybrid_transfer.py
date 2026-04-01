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
    q10, q25, q50, q75, q90 = np.percentile(values, [10, 25, 50, 75, 90])
    return {
        "meta_count": float(values.size),
        "meta_mean": float(values.mean()),
        "meta_std": float(values.std()),
        "meta_min": float(values.min()),
        "meta_max": float(values.max()),
        "meta_range": float(values.max() - values.min()),
        "meta_q10": float(q10),
        "meta_q25": float(q25),
        "meta_q50": float(q50),
        "meta_q75": float(q75),
        "meta_q90": float(q90),
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
        split = split_index.get(f"{dataset_id}:{token}")
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
                valence_coarse=_valence_coarse(int(row.get("valence_score", 5))),
                features=meta,
            )
        )
    return rows


def _to_matrix(rows: list[Example], feature_names: list[str]) -> np.ndarray:
    x = np.zeros((len(rows), len(feature_names)), dtype=float)
    for i, row in enumerate(rows):
        for j, name in enumerate(feature_names):
            x[i, j] = float(row.features.get(name, 0.0))
    x = np.nan_to_num(x, nan=0.0, posinf=1e6, neginf=-1e6)
    x = np.clip(x, -1e6, 1e6)
    return x


def _score(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    cls = compute_classification_metrics(y_true, y_pred)
    yt = [CLASS_TO_SCORE[item] for item in y_true]
    yp = [CLASS_TO_SCORE.get(item, 5) for item in y_pred]
    return {
        "macro_f1": float(cls.macro_f1),
        "balanced_accuracy": float(cls.balanced_accuracy),
        "qwk": float(compute_quadratic_weighted_kappa(yt, yp, min_rating=1, max_rating=9)),
    }


def _covariance(x: np.ndarray) -> np.ndarray:
    if x.shape[0] < 2:
        return np.eye(x.shape[1], dtype=float)
    c = x - x.mean(axis=0, keepdims=True)
    c = np.clip(np.nan_to_num(c, nan=0.0, posinf=1e3, neginf=-1e3), -1e3, 1e3)
    with np.errstate(all="ignore"):
        cov = (c.T @ c) / float(max(x.shape[0] - 1, 1))
    cov = np.nan_to_num(cov, nan=0.0, posinf=1e6, neginf=-1e6)
    return cov


def _matrix_sqrt(matrix: np.ndarray, inverse: bool) -> np.ndarray:
    matrix = np.clip(np.nan_to_num(matrix, nan=0.0, posinf=1e6, neginf=-1e6), -1e6, 1e6)
    eps = 1e-5
    vals, vecs = np.linalg.eigh(matrix + eps * np.eye(matrix.shape[0], dtype=float))
    vals = np.maximum(vals, eps)
    diag = np.diag(1.0 / np.sqrt(vals) if inverse else np.sqrt(vals))
    with np.errstate(all="ignore"):
        out = vecs @ diag @ vecs.T
    out = np.clip(np.nan_to_num(out, nan=0.0, posinf=1e6, neginf=-1e6), -1e6, 1e6)
    return out


def _coral_align(source_x: np.ndarray, target_ref_x: np.ndarray, target_eval_x: np.ndarray) -> np.ndarray:
    s_mean = source_x.mean(axis=0, keepdims=True)
    t_mean = target_ref_x.mean(axis=0, keepdims=True)
    s_cov = _covariance(source_x)
    t_cov = _covariance(target_ref_x)
    s_sqrt = _matrix_sqrt(s_cov, inverse=False)
    t_inv = _matrix_sqrt(t_cov, inverse=True)
    centered = np.clip(np.nan_to_num(target_eval_x - t_mean, nan=0.0, posinf=1e6, neginf=-1e6), -1e6, 1e6)
    with np.errstate(all="ignore"):
        x = centered @ t_inv @ s_sqrt
    x = np.clip(np.nan_to_num(x + s_mean, nan=0.0, posinf=1e6, neginf=-1e6), -1e6, 1e6)
    return x


def _feature_shift(source_x: np.ndarray, target_x: np.ndarray) -> np.ndarray:
    s_mean, t_mean = source_x.mean(axis=0), target_x.mean(axis=0)
    s_std, t_std = source_x.std(axis=0), target_x.std(axis=0)
    pooled = np.sqrt((s_std**2 + t_std**2) / 2.0)
    pooled = np.where(pooled <= 1e-6, 1e-6, pooled)
    mean_diff = np.abs(s_mean - t_mean) / pooled
    ratio = np.maximum(s_std / np.where(t_std <= 1e-6, 1e-6, t_std), t_std / np.where(s_std <= 1e-6, 1e-6, s_std))
    score = mean_diff + np.maximum(0.0, ratio - 1.0)
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
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    feature_context = _new_signal_feature_context(args.artifacts_root)
    data: dict[str, list[Example]] = {}
    for ds, dv in DATASETS:
        data[ds] = _load_examples(args.artifacts_root, ds, dv, args.min_confidence, feature_context)
    feature_names = sorted(next(iter(data.values()))[0].features.keys())

    rows: list[dict[str, Any]] = []
    weights_rows: list[dict[str, Any]] = []
    for source in ("wesad", "grex"):
        source_train = [r for r in data[source] if r.split == "train"]
        y_source = [r.valence_coarse for r in source_train]
        x_source = _to_matrix(source_train, feature_names)
        for target in ("wesad", "grex", "emowear"):
            target_ref = [r for r in data[target] if r.split in ("train", "validation")]
            target_test = [r for r in data[target] if r.split == "test"]
            if not target_ref or not target_test:
                continue
            x_ref = _to_matrix(target_ref, feature_names)
            x_test = _to_matrix(target_test, feature_names)
            y_test = [r.valence_coarse for r in target_test]

            shift = _feature_shift(x_source, x_ref)
            # Soft weights: keep all features, down-weight high-shift features.
            soft_w = np.exp(-args.soft_lambda * np.clip(shift, 0.0, 10.0))
            soft_w = np.clip(soft_w, 0.15, 1.0)
            weights_rows.append(
                {
                    "source_dataset": source,
                    "target_dataset": target,
                    "mean_shift": float(np.mean(shift)),
                    "mean_weight": float(np.mean(soft_w)),
                    "min_weight": float(np.min(soft_w)),
                    "max_weight": float(np.max(soft_w)),
                }
            )

            x_source_w = x_source * soft_w
            x_ref_w = x_ref * soft_w
            x_test_w = x_test * soft_w
            x_test_hybrid = _coral_align(source_x=x_source_w, target_ref_x=x_ref_w, target_eval_x=x_test_w)

            for kind in CLASSIFIERS:
                model = build_estimator_classifier(kind)
                model.fit(x_source_w, y_source)
                pred = [str(v) for v in model.predict(x_test_hybrid)]
                m = _score(y_test, pred)
                rows.append(
                    {
                        "source_dataset": source,
                        "target_dataset": target,
                        "classifier_kind": kind,
                        "macro_f1": round(m["macro_f1"], 6),
                        "balanced_accuracy": round(m["balanced_accuracy"], 6),
                        "qwk": round(m["qwk"], 6),
                        "support": len(y_test),
                    }
                )

    trusted: list[dict[str, Any]] = []
    for kind in CLASSIFIERS:
        wg = next((r for r in rows if r["source_dataset"] == "wesad" and r["target_dataset"] == "grex" and r["classifier_kind"] == kind), None)
        gw = next((r for r in rows if r["source_dataset"] == "grex" and r["target_dataset"] == "wesad" and r["classifier_kind"] == kind), None)
        if wg is None or gw is None:
            continue
        min_cross = min(float(wg["macro_f1"]), float(gw["macro_f1"]))
        trusted.append(
            {
                "classifier_kind": kind,
                "wesad_to_grex_macro_f1": wg["macro_f1"],
                "grex_to_wesad_macro_f1": gw["macro_f1"],
                "min_cross_macro_f1": round(min_cross, 6),
                "is_trusted": bool(min_cross >= args.trusted_floor),
            }
        )

    trusted_models = [r["classifier_kind"] for r in trusted if bool(r["is_trusted"])]
    decision = "revisit_limited_production" if trusted_models else "keep_exploratory"

    _write_csv(out / "model-comparison.csv", rows)
    _write_csv(out / "soft-weights-summary.csv", weights_rows)
    _write_csv(out / "trusted-models.csv", trusted)

    report = {
        "experiment_id": f"e2-8-valence-hybrid-transfer-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "trusted_floor": args.trusted_floor,
        "soft_lambda": args.soft_lambda,
        "trusted_models": trusted_models,
        "summary": trusted,
    }
    (out / "evaluation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# E2.8 Hybrid Transfer Re-gate",
        "",
        f"- Decision: `{decision}`",
        f"- Trusted floor: `{args.trusted_floor}`",
        f"- soft_lambda: `{args.soft_lambda}`",
    ]
    for row in trusted:
        lines.append(
            f"- `{row['classifier_kind']}`: `wesad->grex={float(row['wesad_to_grex_macro_f1']):.6f}`, "
            f"`grex->wesad={float(row['grex_to_wesad_macro_f1']):.6f}`, "
            f"`min={float(row['min_cross_macro_f1']):.6f}`, trusted=`{row['is_trusted']}`"
        )
    (out / "research-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E2.8 hybrid transfer adaptation")
    parser.add_argument("--artifacts-root", type=Path, default=Path("/Users/kgz/Desktop/p/on-go/data/external"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate"),
    )
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--trusted-floor", type=float, default=0.40)
    parser.add_argument("--soft-lambda", type=float, default=0.35)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
