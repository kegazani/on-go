from __future__ import annotations

import json
from pathlib import Path

from inference_api.loader import load_model_bundle, predict


class DummyModel:
    def __init__(self, label: str) -> None:
        self.label = label

    def predict(self, x):  # noqa: ANN001
        return [self.label]


def _write_feature_names(path: Path, names: list[str]) -> None:
    path.write_text(json.dumps({"feature_names": names}), encoding="utf-8")


def test_load_model_bundle_reads_manifest_with_per_track_features(tmp_path, monkeypatch) -> None:
    manifest = {
        "manifest_version": "1.0.0",
        "bundle_id": "fusion-runtime-v1",
        "required_live_streams": ["watch_accelerometer", "polar_hr"],
        "optional_live_streams": ["polar_rr"],
        "direct_outputs": {
            "activity": {
                "model_path": "activity.joblib",
                "feature_names_path": "activity_features.json",
                "feature_profile": "watch_motion_v1",
                "classifier_kind": "ada_boost",
                "modality_group": "watch_only",
            },
            "arousal_coarse": {
                "model_path": "arousal.joblib",
                "feature_names_path": "fusion_features.json",
                "feature_profile": "polar_watch_fusion_v1",
                "classifier_kind": "catboost",
                "modality_group": "fusion",
            },
            "valence_coarse": {
                "model_path": "valence.joblib",
                "feature_names_path": "fusion_features.json",
                "feature_profile": "polar_watch_fusion_v1",
                "classifier_kind": "ridge_classifier",
                "modality_group": "fusion",
            },
        },
    }
    (tmp_path / "model-bundle.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _write_feature_names(tmp_path / "activity_features.json", ["watch_acc_mean"])
    _write_feature_names(tmp_path / "fusion_features.json", ["watch_acc_mean", "polar_hr_mean"])
    for name in ("activity.joblib", "arousal.joblib", "valence.joblib"):
        (tmp_path / name).write_bytes(b"stub")

    monkeypatch.setattr(
        "inference_api.loader.joblib.load",
        lambda path: DummyModel(Path(path).stem),
    )

    bundle = load_model_bundle(tmp_path)

    assert bundle.uses_manifest is True
    assert bundle.bundle_id == "fusion-runtime-v1"
    assert bundle.activity.feature_names == ["watch_acc_mean"]
    assert bundle.arousal_coarse.feature_names == ["watch_acc_mean", "polar_hr_mean"]
    assert bundle.valence_coarse is not None
    assert bundle.required_live_streams == ("watch_accelerometer", "polar_hr")


def test_predict_uses_track_specific_feature_spaces() -> None:
    from inference_api.loader import LoadedBundle, LoadedTrack

    activity = LoadedTrack(
        target_name="activity",
        model=DummyModel("rest"),
        feature_names=["watch_acc_mean"],
        model_path=Path("/tmp/activity.joblib"),
        feature_names_path=Path("/tmp/activity_features.json"),
    )
    arousal = LoadedTrack(
        target_name="arousal_coarse",
        model=DummyModel("high"),
        feature_names=["watch_acc_mean", "polar_hr_mean"],
        model_path=Path("/tmp/arousal.joblib"),
        feature_names_path=Path("/tmp/arousal_features.json"),
    )
    valence = LoadedTrack(
        target_name="valence_coarse",
        model=DummyModel("positive"),
        feature_names=["polar_hr_mean"],
        model_path=Path("/tmp/valence.joblib"),
        feature_names_path=Path("/tmp/valence_features.json"),
    )
    bundle = LoadedBundle(
        activity=activity,
        arousal_coarse=arousal,
        valence_coarse=valence,
        bundle_id="bundle",
        manifest_version="1.0.0",
        uses_manifest=True,
        required_live_streams=(),
        optional_live_streams=(),
        raw_bundle={},
    )

    result = predict(bundle, {"watch_acc_mean": 0.3, "polar_hr_mean": 71.0})

    assert result == {
        "activity": "rest",
        "arousal_coarse": "high",
        "valence_coarse": "positive",
    }
