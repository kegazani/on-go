from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

_MANIFEST_FILENAME = "model-bundle.manifest.json"
_LEGACY_ACTIVITY_FILENAME = "watch_only_centroid_activity.joblib"
_LEGACY_AROUSAL_FILENAME = "watch_only_centroid_arousal.joblib"
_LEGACY_VALENCE_FILENAME = "watch_only_centroid_valence.joblib"
_LEGACY_FEATURES_FILENAME = "feature_names.json"


@dataclass(frozen=True)
class LoadedTrack:
    target_name: str
    model: object
    feature_names: list[str]
    model_path: Path
    feature_names_path: Path
    classifier_kind: str | None = None
    feature_profile: str | None = None
    modality_group: str | None = None


@dataclass(frozen=True)
class LoadedBundle:
    activity: LoadedTrack
    arousal_coarse: LoadedTrack
    valence_coarse: LoadedTrack | None
    bundle_id: str
    manifest_version: str
    uses_manifest: bool
    required_live_streams: tuple[str, ...]
    optional_live_streams: tuple[str, ...]
    raw_bundle: dict[str, Any]


def load_model_bundle(model_dir: Path) -> LoadedBundle:
    manifest_path = model_dir / _MANIFEST_FILENAME
    if manifest_path.exists():
        return _load_manifest_bundle(manifest_path)
    return _load_legacy_bundle(model_dir)


def _load_manifest_bundle(manifest_path: Path) -> LoadedBundle:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    direct_outputs = raw.get("direct_outputs")
    if not isinstance(direct_outputs, dict):
        raise ValueError(f"manifest direct_outputs missing or invalid: {manifest_path}")

    activity = _load_manifest_track(manifest_path, direct_outputs, "activity")
    arousal = _load_manifest_track(manifest_path, direct_outputs, "arousal_coarse")
    valence = None
    if isinstance(direct_outputs.get("valence_coarse"), dict):
        valence = _load_manifest_track(manifest_path, direct_outputs, "valence_coarse")

    return LoadedBundle(
        activity=activity,
        arousal_coarse=arousal,
        valence_coarse=valence,
        bundle_id=str(raw.get("bundle_id", manifest_path.parent.name or "runtime-bundle")),
        manifest_version=str(raw.get("manifest_version", "1.0.0")),
        uses_manifest=True,
        required_live_streams=_as_str_tuple(raw.get("required_live_streams")),
        optional_live_streams=_as_str_tuple(raw.get("optional_live_streams")),
        raw_bundle=raw,
    )


def _load_manifest_track(manifest_path: Path, direct_outputs: dict[str, Any], target_name: str) -> LoadedTrack:
    block = direct_outputs.get(target_name)
    if not isinstance(block, dict):
        raise ValueError(f"manifest track missing: {target_name}")

    model_path = _resolve_relative_path(manifest_path, block.get("model_path"), f"{target_name}.model_path")
    feature_names_path = _resolve_relative_path(
        manifest_path,
        block.get("feature_names_path"),
        f"{target_name}.feature_names_path",
    )
    if not model_path.exists():
        raise FileNotFoundError(f"{target_name} model not found: {model_path}")
    if not feature_names_path.exists():
        raise FileNotFoundError(f"{target_name} feature_names not found: {feature_names_path}")

    model = joblib.load(model_path)
    feature_names = _load_feature_names(feature_names_path)
    return LoadedTrack(
        target_name=target_name,
        model=model,
        feature_names=feature_names,
        model_path=model_path,
        feature_names_path=feature_names_path,
        classifier_kind=_as_optional_str(block.get("classifier_kind")),
        feature_profile=_as_optional_str(block.get("feature_profile")),
        modality_group=_as_optional_str(block.get("modality_group")),
    )


def _load_legacy_bundle(model_dir: Path) -> LoadedBundle:
    activity_path = model_dir / _LEGACY_ACTIVITY_FILENAME
    arousal_path = model_dir / _LEGACY_AROUSAL_FILENAME
    valence_path = model_dir / _LEGACY_VALENCE_FILENAME
    features_path = model_dir / _LEGACY_FEATURES_FILENAME

    if not activity_path.exists():
        raise FileNotFoundError(f"activity model not found: {activity_path}")
    if not arousal_path.exists():
        raise FileNotFoundError(f"arousal model not found: {arousal_path}")
    if not features_path.exists():
        raise FileNotFoundError(f"feature_names not found: {features_path}")

    feature_names = _load_feature_names(features_path)
    activity = LoadedTrack(
        target_name="activity",
        model=joblib.load(activity_path),
        feature_names=feature_names,
        model_path=activity_path,
        feature_names_path=features_path,
        classifier_kind="centroid",
        feature_profile="watch_only_legacy_v1",
        modality_group="watch_only",
    )
    arousal = LoadedTrack(
        target_name="arousal_coarse",
        model=joblib.load(arousal_path),
        feature_names=feature_names,
        model_path=arousal_path,
        feature_names_path=features_path,
        classifier_kind="centroid",
        feature_profile="watch_only_legacy_v1",
        modality_group="watch_only",
    )
    valence = None
    if valence_path.exists():
        valence = LoadedTrack(
            target_name="valence_coarse",
            model=joblib.load(valence_path),
            feature_names=feature_names,
            model_path=valence_path,
            feature_names_path=features_path,
            classifier_kind="centroid",
            feature_profile="watch_only_legacy_v1",
            modality_group="watch_only",
        )

    return LoadedBundle(
        activity=activity,
        arousal_coarse=arousal,
        valence_coarse=valence,
        bundle_id="watch_only_legacy_bundle",
        manifest_version="legacy",
        uses_manifest=False,
        required_live_streams=("watch_heart_rate", "watch_accelerometer"),
        optional_live_streams=(),
        raw_bundle={},
    )


def _load_feature_names(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    feature_names = raw.get("feature_names")
    if not isinstance(feature_names, list) or not all(isinstance(item, str) for item in feature_names):
        raise ValueError(f"invalid feature_names payload: {path}")
    return [str(item) for item in feature_names]


def _resolve_relative_path(manifest_path: Path, raw_value: object, field_name: str) -> Path:
    if not isinstance(raw_value, str) or not raw_value:
        raise ValueError(f"manifest field missing: {field_name}")
    return (manifest_path.parent / raw_value).resolve()


def _as_str_tuple(raw_value: object) -> tuple[str, ...]:
    if not isinstance(raw_value, list):
        return ()
    return tuple(str(item) for item in raw_value if isinstance(item, str) and item)


def _as_optional_str(raw_value: object) -> str | None:
    if isinstance(raw_value, str) and raw_value:
        return raw_value
    return None


def _to_feature_array(feature_vector: dict[str, float], feature_names: list[str]) -> np.ndarray:
    arr = np.zeros((1, len(feature_names)), dtype=float)
    for i, name in enumerate(feature_names):
        arr[0, i] = float(feature_vector.get(name, 0.0))
    return arr


def _predict_track(track: LoadedTrack, feature_vector: dict[str, float]) -> str:
    x = _to_feature_array(feature_vector, track.feature_names)
    pred = track.model.predict(x)
    if len(pred) == 0:
        return ""
    return str(pred[0])


def predict(bundle: LoadedBundle, feature_vector: dict[str, float]) -> dict[str, str]:
    result = {
        "activity": _predict_track(bundle.activity, feature_vector),
        "arousal_coarse": _predict_track(bundle.arousal_coarse, feature_vector),
    }
    if bundle.valence_coarse is not None:
        result["valence_coarse"] = _predict_track(bundle.valence_coarse, feature_vector)
    else:
        result["valence_coarse"] = ""
    return result
