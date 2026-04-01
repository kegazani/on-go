from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from modeling_baselines.audit import run_wesad_safety_audit
from modeling_baselines.multi_dataset import (
    run_multi_dataset_benchmark,
    run_multi_dataset_self_training_execution,
    run_multi_dataset_self_training_scaffold,
    run_multi_dataset_training_protocol,
    run_multi_dataset_training_strategy,
)
from modeling_baselines.pipeline import (
    PipelinePaths,
    run_e2_3_wesad_polar_watch_benchmark,
    run_g3_wesad_comparative_report,
    run_g3_1_wesad_extended_model_zoo,
    run_g3_1_wesad_loso,
    run_h5_weak_label_label_free_wesad,
    run_h3_full_personalization_wesad,
    run_h2_light_personalization_wesad,
    run_m7_3_polar_first_training_dataset_build,
    run_m7_4_runtime_candidate_gate,
    run_m7_5_runtime_bundle_export,
    run_m7_9_polar_expanded_fusion_benchmark,
    run_m7_9_runtime_bundle_export,
    run_fusion_wesad_comparison,
    run_watch_only_wesad_baseline,
)
from modeling_baselines.tracking import (
    create_tracking_context,
    _flatten_metrics,
)


def run() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    paths = PipelinePaths(
        segment_labels_path=args.segment_labels,
        split_manifest_path=args.split_manifest,
        raw_wesad_root=args.wesad_raw_root,
        output_dir=args.output_dir,
    )

    tracking_enabled = not args.no_mlflow
    tracking_uri = args.mlflow_tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")
    ctx, _ = create_tracking_context(
        enabled=tracking_enabled,
        experiment_name="on-go-modeling-baselines",
        tracking_uri=tracking_uri,
        run_name=None,
        tags={"phase": "modeling", "run_kind": args.run_kind},
    )
    if tracking_enabled:
        ctx.log_params({
            "run_kind": args.run_kind,
            "dataset_id": args.dataset_id,
            "dataset_version": args.dataset_version,
            "preprocessing_version": args.preprocessing_version,
            "min_confidence": str(args.min_confidence),
            "segment_labels_path": str(args.segment_labels),
            "split_manifest_path": str(args.split_manifest),
            "output_dir": str(args.output_dir),
            "registry_path": str(args.registry_path),
        })
        if args.run_kind == "m7-5-runtime-bundle-export":
            ctx.log_params({
                "runtime_candidate_verdict": str(
                    args.runtime_candidate_verdict
                    or (args.output_dir / args.dataset_id / args.dataset_version / "m7-4-runtime-candidate-gate" / "runtime-candidate-verdict.json")
                )
            })
        if args.run_kind in ("h2-light-personalization-wesad", "h3-full-personalization-wesad", "h5-weak-label-label-free-wesad"):
            ctx.log_params({
                "calibration_segments": str(args.calibration_segments),
                "adaptation_weight": str(args.adaptation_weight),
            })

    if args.run_kind == "audit-wesad":
        result = run_wesad_safety_audit(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "fusion-wesad":
        result = run_fusion_wesad_comparison(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "e2-3-wesad-polar-watch-benchmark":
        result = run_e2_3_wesad_polar_watch_benchmark(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind in ("m7-3-polar-first-training-dataset-build", "polar-first-training-dataset-build"):
        result = run_m7_3_polar_first_training_dataset_build(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "m7-4-runtime-candidate-gate":
        result = run_m7_4_runtime_candidate_gate(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "m7-5-runtime-bundle-export":
        result = run_m7_5_runtime_bundle_export(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
            runtime_candidate_verdict_path=args.runtime_candidate_verdict,
        )
    elif args.run_kind == "m7-9-polar-expanded-fusion-benchmark":
        result = run_m7_9_polar_expanded_fusion_benchmark(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "m7-9-runtime-bundle-export":
        m79_overrides: dict[str, str] = {}
        if getattr(args, "m79_override_activity_variant", None):
            m79_overrides["activity"] = str(args.m79_override_activity_variant)
        if getattr(args, "m79_override_arousal_variant", None):
            m79_overrides["arousal_coarse"] = str(args.m79_override_arousal_variant)
        if getattr(args, "m79_override_valence_variant", None):
            m79_overrides["valence_coarse"] = str(args.m79_override_valence_variant)
        result = run_m7_9_runtime_bundle_export(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
            track_variant_overrides=m79_overrides or None,
        )
    elif args.run_kind == "g3-1-wesad":
        result = run_g3_1_wesad_extended_model_zoo(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "g3-1-wesad-loso":
        result = run_g3_1_wesad_loso(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "g3-wesad":
        result = run_g3_wesad_comparative_report(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "h2-light-personalization-wesad":
        result = run_h2_light_personalization_wesad(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
            calibration_segments=args.calibration_segments,
        )
    elif args.run_kind == "h3-full-personalization-wesad":
        result = run_h3_full_personalization_wesad(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
            calibration_segments=args.calibration_segments,
            adaptation_weight=args.adaptation_weight,
        )
    elif args.run_kind == "h5-weak-label-label-free-wesad":
        result = run_h5_weak_label_label_free_wesad(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
            calibration_segments=args.calibration_segments,
            adaptation_weight=args.adaptation_weight,
        )
    elif args.run_kind == "g3-2-multi-dataset":
        result = run_multi_dataset_benchmark(
            artifacts_root=args.output_dir,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "g3-2-multi-dataset-strategy":
        result = run_multi_dataset_training_strategy(
            artifacts_root=args.output_dir,
            registry_path=args.registry_path,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "g3-2-multi-dataset-protocol":
        result = run_multi_dataset_training_protocol(
            artifacts_root=args.output_dir,
            registry_path=args.registry_path,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "g3-2-self-training-scaffold":
        result = run_multi_dataset_self_training_scaffold(
            artifacts_root=args.output_dir,
            registry_path=args.registry_path,
            min_confidence=args.min_confidence,
        )
    elif args.run_kind == "g3-2-self-training-execution":
        result = run_multi_dataset_self_training_execution(
            artifacts_root=args.output_dir,
            registry_path=args.registry_path,
            min_confidence=args.min_confidence,
        )
    else:
        model_save_dir = None
        if args.save_models and args.run_kind == "watch-only-wesad":
            model_save_dir = (
                paths.output_dir
                / args.dataset_id
                / args.dataset_version
                / "watch-only-baseline"
                / "models"
            )
        result = run_watch_only_wesad_baseline(
            paths=paths,
            dataset_id=args.dataset_id,
            dataset_version=args.dataset_version,
            preprocessing_version=args.preprocessing_version,
            min_confidence=args.min_confidence,
            model_save_dir=model_save_dir,
        )

    if tracking_enabled and "experiment_id" in result:
        ctx.set_tag("experiment_id", result["experiment_id"])
        report_path = result.get("report_path") or result.get("research_report_path")
        if report_path:
            report_file = Path(report_path)
            if report_file.suffix == ".json" and report_file.exists():
                report = json.loads(report_file.read_text(encoding="utf-8"))
                flat = _flatten_metrics(report.get("tracks") or report)
                if flat:
                    ctx.log_metrics(flat)
        output_root = _output_root_from_result(result)
        if output_root and output_root.exists():
            ctx.log_artifacts(output_root, artifact_path="artifacts")

    if tracking_enabled:
        import mlflow
        mlflow.end_run()

    print(json.dumps(result, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="on-go-modeling-baselines",
        description="Run baseline modeling pipelines for WESAD dataset",
    )
    parser.add_argument(
        "--run-kind",
        choices=[
            "audit-wesad",
            "watch-only-wesad",
            "fusion-wesad",
            "e2-3-wesad-polar-watch-benchmark",
            "m7-3-polar-first-training-dataset-build",
            "polar-first-training-dataset-build",
            "m7-4-runtime-candidate-gate",
            "m7-5-runtime-bundle-export",
            "m7-9-polar-expanded-fusion-benchmark",
            "m7-9-runtime-bundle-export",
            "g3-wesad",
            "g3-1-wesad",
            "g3-1-wesad-loso",
            "g3-2-multi-dataset",
            "g3-2-multi-dataset-strategy",
            "g3-2-multi-dataset-protocol",
            "g3-2-self-training-scaffold",
            "g3-2-self-training-execution",
            "h2-light-personalization-wesad",
            "h3-full-personalization-wesad",
            "h5-weak-label-label-free-wesad",
        ],
        default="watch-only-wesad",
        help="Pipeline variant to execute.",
    )
    parser.add_argument(
        "--segment-labels",
        type=Path,
        required=True,
        help="Path to unified/segment-labels.jsonl",
    )
    parser.add_argument(
        "--split-manifest",
        type=Path,
        required=True,
        help="Path to manifest/split-manifest.json",
    )
    parser.add_argument(
        "--wesad-raw-root",
        type=Path,
        required=True,
        help="Path to raw WESAD directory with S*/S*.pkl files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output root for experiment artifacts",
    )
    parser.add_argument("--dataset-id", default="wesad")
    parser.add_argument("--dataset-version", default="wesad-v1")
    parser.add_argument("--preprocessing-version", default="e2-v1")
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=_default_registry_path(),
        help="Path to dataset-registry JSONL for multi-dataset strategy runs.",
    )
    parser.add_argument(
        "--runtime-candidate-verdict",
        type=Path,
        default=None,
        help="Path to m7-4 runtime-candidate-verdict.json (defaults to the standard output_dir location).",
    )
    parser.add_argument(
        "--calibration-segments",
        type=int,
        default=2,
        help="Per-subject calibration segment budget for light personalization runs.",
    )
    parser.add_argument(
        "--adaptation-weight",
        type=int,
        default=5,
        help="Calibration sample repetition factor for full personalization refit runs.",
    )
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Disable MLflow experiment tracking.",
    )
    parser.add_argument(
        "--mlflow-tracking-uri",
        type=str,
        default=None,
        help="MLflow tracking URI (default: MLFLOW_TRACKING_URI or ./mlruns).",
    )
    parser.add_argument(
        "--save-models",
        action="store_true",
        help="Persist trained models to output_dir (watch-only run). Enables model registry.",
    )
    parser.add_argument(
        "--m79-override-activity-variant",
        default=None,
        help="M7.9 runtime export: force variant for activity (polar_cardio_only, watch_motion_only, polar_expanded_fusion).",
    )
    parser.add_argument(
        "--m79-override-arousal-variant",
        default=None,
        help="M7.9 runtime export: force variant for arousal_coarse (use polar_expanded_fusion for unified fusion).",
    )
    parser.add_argument(
        "--m79-override-valence-variant",
        default=None,
        help="M7.9 runtime export: force variant for valence_coarse.",
    )
    return parser


def _default_registry_path() -> Path:
    return Path(__file__).resolve().parents[4] / "services" / "dataset-registry" / "registry" / "datasets.jsonl"


def _output_root_from_result(result: dict) -> Path | None:
    report_path = result.get("report_path") or result.get("research_report_path")
    if not report_path:
        return None
    p = Path(report_path)
    return p.parent if p.exists() else None


if __name__ == "__main__":
    run()
