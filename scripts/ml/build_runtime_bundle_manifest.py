from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _csv_to_list(raw: str) -> list[str]:
    items = [item.strip() for item in raw.split(",")]
    return [item for item in items if item]


def _manifest_path_value(output_dir: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(output_dir.resolve()))
    except ValueError:
        return str(resolved)


def _track_block(
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
        "model_path": _manifest_path_value(output_dir, model_path),
        "feature_names_path": _manifest_path_value(output_dir, feature_names_path),
        "classifier_kind": classifier_kind,
        "feature_profile": feature_profile,
        "modality_group": modality_group,
    }
    if policy_scope:
        block["policy_scope"] = policy_scope
    return block


def run() -> None:
    parser = argparse.ArgumentParser(
        prog="build_runtime_bundle_manifest",
        description="Build model-bundle.manifest.json for inference/live-inference runtime bundle.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bundle-id", type=str, required=True)
    parser.add_argument("--bundle-version", type=str, default="v1")
    parser.add_argument("--manifest-version", type=str, default="1.0.0")
    parser.add_argument("--required-live-streams", type=str, default="watch_accelerometer,polar_hr")
    parser.add_argument("--optional-live-streams", type=str, default="watch_heart_rate,polar_rr,watch_activity_context,watch_hrv")
    parser.add_argument("--notes", type=str, default="")

    parser.add_argument("--activity-model", type=Path, required=True)
    parser.add_argument("--activity-features", type=Path, required=True)
    parser.add_argument("--activity-classifier-kind", type=str, required=True)
    parser.add_argument("--activity-feature-profile", type=str, required=True)
    parser.add_argument("--activity-modality-group", type=str, default="watch_only")

    parser.add_argument("--arousal-model", type=Path, required=True)
    parser.add_argument("--arousal-features", type=Path, required=True)
    parser.add_argument("--arousal-classifier-kind", type=str, required=True)
    parser.add_argument("--arousal-feature-profile", type=str, required=True)
    parser.add_argument("--arousal-modality-group", type=str, default="fusion")

    parser.add_argument("--valence-model", type=Path, default=None)
    parser.add_argument("--valence-features", type=Path, default=None)
    parser.add_argument("--valence-classifier-kind", type=str, default="ridge_classifier")
    parser.add_argument("--valence-feature-profile", type=str, default="fusion_scoped_v1")
    parser.add_argument("--valence-modality-group", type=str, default="fusion")
    parser.add_argument("--valence-policy-scope", type=str, default="internal_scoped")

    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    direct_outputs: dict[str, Any] = {
        "activity": _track_block(
            output_dir=output_dir,
            model_path=args.activity_model,
            feature_names_path=args.activity_features,
            classifier_kind=args.activity_classifier_kind,
            feature_profile=args.activity_feature_profile,
            modality_group=args.activity_modality_group,
        ),
        "arousal_coarse": _track_block(
            output_dir=output_dir,
            model_path=args.arousal_model,
            feature_names_path=args.arousal_features,
            classifier_kind=args.arousal_classifier_kind,
            feature_profile=args.arousal_feature_profile,
            modality_group=args.arousal_modality_group,
        ),
    }

    if args.valence_model is not None or args.valence_features is not None:
        if args.valence_model is None or args.valence_features is None:
            raise ValueError("valence-model and valence-features must be provided together")
        direct_outputs["valence_coarse"] = _track_block(
            output_dir=output_dir,
            model_path=args.valence_model,
            feature_names_path=args.valence_features,
            classifier_kind=args.valence_classifier_kind,
            feature_profile=args.valence_feature_profile,
            modality_group=args.valence_modality_group,
            policy_scope=args.valence_policy_scope,
        )

    payload = {
        "manifest_version": args.manifest_version,
        "bundle_id": args.bundle_id,
        "bundle_version": args.bundle_version,
        "required_live_streams": _csv_to_list(args.required_live_streams),
        "optional_live_streams": _csv_to_list(args.optional_live_streams),
        "direct_outputs": direct_outputs,
        "notes": args.notes,
    }

    out_path = output_dir / "model-bundle.manifest.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_path": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    run()
