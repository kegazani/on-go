from __future__ import annotations

from pathlib import Path

from inference_api.loader import load_model_bundle


def test_active_runtime_bundle_includes_scoped_valence_track() -> None:
    bundle_dir = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "runtime-bundles"
        / "k5-9-fusion-runtime-v4-live-feature-aligned"
    )

    bundle = load_model_bundle(bundle_dir)

    assert bundle.bundle_id == "on-go-k5-9-runtime-v4-live-feature-aligned"
    assert bundle.valence_coarse is not None
    assert bundle.valence_coarse.classifier_kind == "ridge_classifier"
    assert bundle.valence_coarse.feature_profile == "live_acc_bvp_only_scoped_valence_v1"
