from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODELING_BASELINES_SRC = ROOT / "services" / "modeling-baselines" / "src"
if str(MODELING_BASELINES_SRC) not in sys.path:
    sys.path.insert(0, str(MODELING_BASELINES_SRC))

from modeling_baselines.estimators import get_classifier_config
from modeling_baselines.metrics import (
    ClassificationMetrics,
    compute_classification_metrics,
    compute_mae,
    compute_quadratic_weighted_kappa,
    compute_spearman_rho,
)
from modeling_baselines.pipeline import (  # noqa: E402
    PipelinePaths,
    _build_classifier,
    _load_examples,
    _to_feature_matrix,
)


def _default_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def _load_feature_names(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    feature_names = raw.get("feature_names")
    if not isinstance(feature_names, list) or not all(isinstance(item, str) for item in feature_names):
        raise ValueError(f"invalid feature_names payload: {path}")
    return [str(item) for item in feature_names]


def _coarse_class_score_mapping(scores: list[int], labels: list[str]) -> dict[str, int]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for score, label in zip(scores, labels):
        grouped[str(label)].append(int(score))

    mapping: dict[str, int] = {}
    for label, raw_scores in grouped.items():
        if not raw_scores:
            continue
        median = int(round(float(np.median(np.asarray(raw_scores, dtype=float)))))
        mapping[label] = max(1, min(9, median))
    return mapping


def _metrics_payload(metrics: ClassificationMetrics) -> dict[str, object]:
    return {
        "macro_f1": metrics.macro_f1,
        "balanced_accuracy": metrics.balanced_accuracy,
        "weighted_f1": metrics.weighted_f1,
        "macro_recall": metrics.macro_recall,
        "labels": metrics.labels,
        "per_class_support": metrics.per_class_support,
        "confusion_matrix": metrics.confusion_matrix,
    }


def run() -> None:
    parser = argparse.ArgumentParser(
        prog="export_live_valence_track",
        description="Train and export a scoped valence model on the live-aligned watch_acc + watch_bvp feature space.",
    )
    parser.add_argument(
        "--segment-labels",
        type=Path,
        default=_default_path("data", "external", "wesad", "artifacts", "wesad", "wesad-v1", "unified", "segment-labels.jsonl"),
    )
    parser.add_argument(
        "--split-manifest",
        type=Path,
        default=_default_path("data", "external", "wesad", "artifacts", "wesad", "wesad-v1", "manifest", "split-manifest.json"),
    )
    parser.add_argument(
        "--wesad-raw-root",
        type=Path,
        default=_default_path("data", "external", "wesad", "raw"),
    )
    parser.add_argument(
        "--feature-names-source",
        type=Path,
        default=_default_path(
            "data",
            "runtime-bundles",
            "k5-9-fusion-runtime-v4-live-feature-aligned",
            "arousal_feature_names.json",
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_path("data", "runtime-bundles", "k5-9-fusion-runtime-v4-live-feature-aligned"),
    )
    parser.add_argument("--model-name", type=str, default="valence_watch_acc_bvp_ridge_classifier.joblib")
    parser.add_argument("--feature-names-name", type=str, default="valence_feature_names.json")
    parser.add_argument("--report-name", type=str, default="valence_watch_acc_bvp_ridge_classifier.report.json")
    parser.add_argument("--dataset-id", type=str, default="wesad")
    parser.add_argument("--dataset-version", type=str, default="wesad-v1")
    parser.add_argument("--classifier-kind", type=str, default="ridge_classifier")
    parser.add_argument("--min-confidence", type=float, default=0.7)

    args = parser.parse_args()

    paths = PipelinePaths(
        segment_labels_path=args.segment_labels,
        split_manifest_path=args.split_manifest,
        raw_wesad_root=args.wesad_raw_root,
        output_dir=args.output_dir,
    )
    examples, _, split_manifest = _load_examples(
        paths=paths,
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
        min_confidence=args.min_confidence,
    )

    feature_names = _load_feature_names(args.feature_names_source)
    missing_features = sorted({name for name in feature_names if name not in examples[0].features})
    if missing_features:
        raise ValueError(f"feature set contains names not present in extracted examples: {missing_features}")

    train_examples = [item for item in examples if item.split == "train"]
    validation_examples = [item for item in examples if item.split == "validation"]
    test_examples = [item for item in examples if item.split == "test"]
    fit_examples = train_examples + validation_examples
    if not fit_examples or not test_examples:
        raise ValueError("insufficient split coverage for export")

    x_fit = _to_feature_matrix(fit_examples, feature_names)
    x_test = _to_feature_matrix(test_examples, feature_names)
    y_fit = [item.valence_coarse for item in fit_examples]
    y_test = [item.valence_coarse for item in test_examples]
    y_fit_scores = [item.valence_score for item in fit_examples]
    y_test_scores = [item.valence_score for item in test_examples]

    classifier = _build_classifier(args.classifier_kind)
    classifier.fit(x_fit, y_fit)
    y_pred = classifier.predict(x_test)

    coarse_to_score = _coarse_class_score_mapping(y_fit_scores, y_fit)
    y_pred_scores = [coarse_to_score.get(label, 5) for label in y_pred]
    metrics = compute_classification_metrics(y_test, y_pred)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / args.model_name
    feature_names_path = output_dir / args.feature_names_name
    report_path = output_dir / args.report_name

    joblib.dump(classifier, model_path)
    feature_names_path.write_text(
        json.dumps({"feature_names": feature_names}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    classifier_config = get_classifier_config(args.classifier_kind)
    report = {
        "track": "valence_coarse",
        "dataset_version": f"{args.dataset_id}:{args.dataset_version}",
        "classifier_kind": args.classifier_kind,
        "model_family": classifier_config.model_family,
        "min_confidence": args.min_confidence,
        "feature_names_source": str(args.feature_names_source.resolve()),
        "feature_count": len(feature_names),
        "fit_split_subjects": sorted({item.subject_id for item in fit_examples}),
        "fit_split_segments": len(fit_examples),
        "test_split_subjects": sorted({item.subject_id for item in test_examples}),
        "test_split_segments": len(test_examples),
        "test_label_distribution": dict(sorted(Counter(y_test).items())),
        "coarse_to_score": coarse_to_score,
        "test_metrics": _metrics_payload(metrics),
        "test_ordinal_metrics": {
            "mae": compute_mae(y_test_scores, y_pred_scores),
            "spearman_rho": compute_spearman_rho(y_test_scores, y_pred_scores),
            "quadratic_weighted_kappa": compute_quadratic_weighted_kappa(
                y_test_scores,
                y_pred_scores,
                min_rating=1,
                max_rating=9,
            ),
        },
        "split_manifest_strategy": str(split_manifest.get("strategy", "subject-wise")),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "model_path": str(model_path),
                "feature_names_path": str(feature_names_path),
                "report_path": str(report_path),
                "test_macro_f1": metrics.macro_f1,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
