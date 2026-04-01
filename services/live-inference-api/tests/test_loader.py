from __future__ import annotations

import json
from pathlib import Path

from live_inference_api.loader import load_model_bundle


class DummyModel:
    def __init__(self, label: str) -> None:
        self.label = label

    def predict(self, x):  # noqa: ANN001
        return [self.label]


def _write_feature_names(path: Path, names: list[str]) -> None:
    path.write_text(json.dumps({"feature_names": names}), encoding="utf-8")


def test_load_model_bundle_supports_manifest_runtime_bundle(tmp_path, monkeypatch) -> None:
    manifest = {
        "manifest_version": "1.0.0",
        "bundle_id": "live-fusion-runtime-v1",
        "required_live_streams": ["watch_accelerometer", "polar_hr"],
        "optional_live_streams": ["watch_activity_context", "polar_rr"],
        "direct_outputs": {
            "activity": {
                "model_path": "activity.joblib",
                "feature_names_path": "activity_features.json",
                "feature_profile": "watch_motion_v1",
            },
            "arousal_coarse": {
                "model_path": "arousal.joblib",
                "feature_names_path": "fusion_features.json",
                "feature_profile": "polar_watch_fusion_v1",
            },
        },
    }
    (tmp_path / "model-bundle.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _write_feature_names(tmp_path / "activity_features.json", ["watch_acc_mean"])
    _write_feature_names(tmp_path / "fusion_features.json", ["watch_acc_mean", "polar_hr_mean"])
    for name in ("activity.joblib", "arousal.joblib"):
        (tmp_path / name).write_bytes(b"stub")

    monkeypatch.setattr(
        "live_inference_api.loader.joblib.load",
        lambda path: DummyModel(Path(path).stem),
    )

    bundle = load_model_bundle(tmp_path)

    assert bundle.uses_manifest is True
    assert bundle.bundle_id == "live-fusion-runtime-v1"
    assert bundle.activity.feature_profile == "watch_motion_v1"
    assert bundle.arousal_coarse.feature_profile == "polar_watch_fusion_v1"
    assert bundle.required_live_streams == ("watch_accelerometer", "polar_hr")


def test_m7_5_arousal_bundle_keeps_chest_prefixed_features() -> None:
    bundle_dir = Path(
        "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-5-runtime-bundle-export"
    )
    bundle = load_model_bundle(bundle_dir)

    assert bundle.required_live_streams == ("watch_accelerometer", "polar_hr")
    assert bundle.arousal_coarse.feature_names
    assert len(bundle.arousal_coarse.feature_names) == 25
    assert any(name.startswith("chest_ecg_") for name in bundle.arousal_coarse.feature_names)
    assert any(name.startswith("watch_acc_") for name in bundle.arousal_coarse.feature_names)
    assert all(name.startswith("watch_acc_") for name in bundle.activity.feature_names)
    assert all(name.startswith("watch_acc_") for name in bundle.valence_coarse.feature_names)
